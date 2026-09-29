// cpe_trace.hpp - snapshot recorder injected by app/services/trace/instrument.py.
//
// CPE_SNAP(id, expr, ...) writes ONE JSON line per call to the file descriptor
// named by the CPE_TRACE_FD environment variable:
//   {"id":1,"hit":3,"values":{"arr":[1,2],"i":0},"truncated":["arr"]}
// "truncated" is present only when a container had more than CPE_MAX_ELEMS
// elements (only the first CPE_MAX_ELEMS are written; the value stays a list).
// If CPE_TRACE_FD is unset or not a usable fd, recording is a no-op.
// At most CPE_MAX_HITS snapshots are written per id; later hits are skipped.
#pragma once

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <deque>
#include <queue>
#include <stack>
#include <string>
#include <type_traits>
#include <unordered_map>
#include <vector>

#ifndef CPE_MAX_HITS
#define CPE_MAX_HITS 12
#endif
#ifndef CPE_MAX_ELEMS
#define CPE_MAX_ELEMS 64
#endif

namespace cpe_trace {

template <class T>
struct Arr {
    const T* p;
    long long n;
};

template <class T>
Arr<T> arr(const T* p, long long n) { return Arr<T>{p, n}; }

template <class>
inline constexpr bool unsupported = false;

// Declarations first: calls inside templates on std:: types only find overloads
// declared before the template definition (ADL looks in std, not here).
template <class T> void put(std::string& o, const T& v, bool& tr);
template <class T, class A> void put(std::string& o, const std::vector<T, A>& v, bool& tr);
template <class T, class A> void put(std::string& o, const std::deque<T, A>& v, bool& tr);
template <class T, class C> void put(std::string& o, const std::stack<T, C>& v, bool& tr);
template <class T, class C> void put(std::string& o, const std::queue<T, C>& v, bool& tr);
template <class T> void put(std::string& o, const Arr<T>& v, bool& tr);

inline void put_str(std::string& o, const char* s, size_t n) {
    static const char hex[] = "0123456789abcdef";
    o += '"';
    for (size_t i = 0; i < n; i++) {
        unsigned char c = static_cast<unsigned char>(s[i]);
        switch (c) {
            case '"': o += "\\\""; break;
            case '\\': o += "\\\\"; break;
            case '\n': o += "\\n"; break;
            case '\r': o += "\\r"; break;
            case '\t': o += "\\t"; break;
            default:
                if (c < 0x20) {
                    o += "\\u00";
                    o += hex[c >> 4];
                    o += hex[c & 15];
                } else {
                    o += static_cast<char>(c);  // UTF-8 bytes pass through
                }
        }
    }
    o += '"';
}

template <class T>
void put(std::string& o, const T& v, bool&) {
    if constexpr (std::is_same_v<T, bool>) {
        o += v ? "true" : "false";
    } else if constexpr (std::is_same_v<T, char>) {
        put_str(o, &v, 1);
    } else if constexpr (std::is_integral_v<T> && std::is_signed_v<T>) {
        o += std::to_string(static_cast<long long>(v));
    } else if constexpr (std::is_integral_v<T>) {
        o += std::to_string(static_cast<unsigned long long>(v));
    } else if constexpr (std::is_floating_point_v<T>) {
        double d = static_cast<double>(v);
        if (!std::isfinite(d)) {
            o += "null";
        } else {
            char buf[32];
            std::snprintf(buf, sizeof buf, "%.15g", d);
            o += buf;
        }
    } else if constexpr (std::is_same_v<T, std::string>) {
        put_str(o, v.data(), v.size());
    } else {
        static_assert(unsupported<T>, "CPE_SNAP does not support this type");
    }
}

// Writes the first CPE_MAX_ELEMS items of [0, n) via get(i).
template <class Get>
void put_seq(std::string& o, long long n, Get get, bool& tr) {
    if (n > CPE_MAX_ELEMS) {
        tr = true;
        n = CPE_MAX_ELEMS;
    }
    o += '[';
    for (long long i = 0; i < n; i++) {
        if (i) o += ',';
        get(i);
    }
    o += ']';
}

template <class T, class A>
void put(std::string& o, const std::vector<T, A>& v, bool& tr) {
    // `const T& e = v[i]` also works for vector<bool>, whose operator[] yields a proxy.
    put_seq(o, (long long)v.size(), [&](long long i) { const T& e = v[i]; put(o, e, tr); }, tr);
}

template <class T, class A>
void put(std::string& o, const std::deque<T, A>& v, bool& tr) {
    put_seq(o, (long long)v.size(), [&](long long i) { put(o, v[i], tr); }, tr);
}

template <class T, class C>
void put(std::string& o, const std::stack<T, C>& s, bool& tr) {
    std::stack<T, C> c = s;  // bottom -> top
    std::vector<T> items;
    while (!c.empty()) {
        items.push_back(c.top());
        c.pop();
    }
    long long n = (long long)items.size();
    put_seq(o, n, [&](long long i) { put(o, items[n - 1 - i], tr); }, tr);
}

template <class T, class C>
void put(std::string& o, const std::queue<T, C>& q, bool& tr) {
    std::queue<T, C> c = q;  // front -> back
    std::vector<T> items;
    while (!c.empty()) {
        items.push_back(c.front());
        c.pop();
    }
    put_seq(o, (long long)items.size(), [&](long long i) { put(o, items[i], tr); }, tr);
}

template <class T>
void put(std::string& o, const Arr<T>& a, bool& tr) {
    put_seq(o, a.n < 0 ? 0 : a.n, [&](long long i) { put(o, a.p[i], tr); }, tr);
}

inline std::FILE* out() {
    static std::FILE* f = [] {
        const char* s = std::getenv("CPE_TRACE_FD");
        return s ? fdopen(std::atoi(s), "w") : nullptr;
    }();
    return f;
}

// One map for all snap<Ts...> instantiations.
inline std::unordered_map<int, int>& hit_counts() {
    static std::unordered_map<int, int> m;
    return m;
}

// Splits "a, b[i], CPE_ARR(x, n)" on top-level commas; "CPE_ARR(x, n)" -> "x".
inline std::vector<std::string> split_names(const char* names) {
    std::vector<std::string> res;
    std::string cur;
    int depth = 0;
    for (const char* p = names;; p++) {
        if (*p == '\0' || (*p == ',' && depth == 0)) {
            size_t b = cur.find_first_not_of(' '), e = cur.find_last_not_of(' ');
            cur = b == std::string::npos ? "" : cur.substr(b, e - b + 1);
            if (cur.rfind("CPE_ARR(", 0) == 0) cur = cur.substr(8, cur.find(',') - 8);
            res.push_back(cur);
            cur.clear();
            if (*p == '\0') break;
            continue;
        }
        if (*p == '(' || *p == '[') depth++;
        if (*p == ')' || *p == ']') depth--;
        cur += *p;
    }
    return res;
}

template <class... Ts>
void snap(int id, const char* names, const Ts&... vals) {
    std::FILE* f = out();
    if (!f) return;
    int hit = ++hit_counts()[id];
    if (hit > CPE_MAX_HITS) return;

    std::vector<std::string> keys = split_names(names);
    std::string o = "{\"id\":" + std::to_string(id) + ",\"hit\":" + std::to_string(hit) + ",\"values\":{";
    std::string truncated;
    size_t k = 0;
    auto one = [&](const auto& v) {
        bool tr = false;
        if (k) o += ',';
        put_str(o, keys[k].data(), keys[k].size());
        o += ':';
        put(o, v, tr);
        if (tr) {
            if (!truncated.empty()) truncated += ',';
            put_str(truncated, keys[k].data(), keys[k].size());
        }
        k++;
    };
    (one(vals), ...);
    o += '}';
    if (!truncated.empty()) o += ",\"truncated\":[" + truncated + "]";
    o += "}\n";
    std::fwrite(o.data(), 1, o.size(), f);
    std::fflush(f);
}

}  // namespace cpe_trace

#define CPE_ARR(ptr, len) ::cpe_trace::arr((ptr), (long long)(len))
#define CPE_SNAP(id, ...) ::cpe_trace::snap((id), #__VA_ARGS__, __VA_ARGS__)
