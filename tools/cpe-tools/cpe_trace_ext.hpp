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
#include <algorithm>
#include <deque>
#include <map>
#include <set>
#include <unordered_map>
#include <unordered_set>
#include <queue>
#include <stack>
#include <string>
#include <type_traits>
#include <unordered_map>
#include <vector>

#ifndef CPE_MAX_HITS
#define CPE_MAX_HITS 400
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

template <class T>
struct Arr2 {
    const T* p;
    long long r, c;
};

template <class T>
Arr2<T> arr2(const T* p, long long r, long long c) { return Arr2<T>{p, r, c}; }

// vector<T> g[N]（鄰接表）：N 個 vector 當成不等長的二維列表
template <class T>
struct Arrv {
    const std::vector<T>* p;
    long long n;
};

template <class T>
Arrv<T> arrv(const std::vector<T>* p, long long n) { return Arrv<T>{p, n}; }

// CPE-008：vector<P>（P 為只有基本型別欄位的簡單 struct）的單一欄位視圖：p.s／p.i／p.j 各成一列
template <class V, class F>
struct Fld {
    const V* p;
    F get;
};

template <class V, class F>
Fld<V, F> fld(const V& v, F get) { return Fld<V, F>{&v, get}; }

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
template <class T> void put(std::string& o, const Arr2<T>& v, bool& tr);
template <class T> void put(std::string& o, const Arrv<T>& v, bool& tr);
template <class V, class F> void put(std::string& o, const Fld<V, F>& v, bool& tr);
template <class T, class C, class Cmp> void put(std::string& o, const std::priority_queue<T, C, Cmp>& v, bool& tr);
template <class K, class V, class... R> void put(std::string& o, const std::map<K, V, R...>& v, bool& tr);
template <class K, class V, class... R> void put(std::string& o, const std::unordered_map<K, V, R...>& v, bool& tr);
template <class K, class... R> void put(std::string& o, const std::set<K, R...>& v, bool& tr);
template <class K, class... R> void put(std::string& o, const std::multiset<K, R...>& v, bool& tr);
template <class K, class... R> void put(std::string& o, const std::unordered_set<K, R...>& v, bool& tr);

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

template <class T>
void put(std::string& o, const Arr2<T>& a, bool& tr) {
    long long r = a.r < 0 ? 0 : a.r, c = a.c < 0 ? 0 : a.c;
    put_seq(o, r, [&](long long i) { put_seq(o, c, [&](long long j) { put(o, a.p[i * c + j], tr); }, tr); }, tr);
}

template <class T>
void put(std::string& o, const Arrv<T>& a, bool& tr) {
    put_seq(o, a.n < 0 ? 0 : a.n, [&](long long i) { put(o, a.p[i], tr); }, tr);
}

template <class V, class F>
void put(std::string& o, const Fld<V, F>& a, bool& tr) {
    put_seq(o, (long long)a.p->size(), [&](long long i) { put(o, a.get((*a.p)[i]), tr); }, tr);
}

// priority_queue：由堆頂到堆底（依優先序）
template <class T, class C, class Cmp>
void put(std::string& o, const std::priority_queue<T, C, Cmp>& q, bool& tr) {
    std::priority_queue<T, C, Cmp> c = q;
    std::vector<T> items;
    while (!c.empty()) { items.push_back(c.top()); c.pop(); }
    put_seq(o, (long long)items.size(), [&](long long i) { put(o, items[i], tr); }, tr);
}

// map／unordered_map：[[k,v],...]（依鍵排序）
template <class M>
void put_map(std::string& o, const M& m, bool& tr) {
    std::vector<std::pair<typename M::key_type, typename M::mapped_type>> items(m.begin(), m.end());
    std::sort(items.begin(), items.end(), [](const auto& a, const auto& b) { return a.first < b.first; });
    put_seq(o, (long long)items.size(), [&](long long i) {
        o += '[';
        put(o, items[i].first, tr);
        o += ',';
        put(o, items[i].second, tr);
        o += ']';
    }, tr);
}
template <class K, class V, class... R>
void put(std::string& o, const std::map<K, V, R...>& v, bool& tr) { put_map(o, v, tr); }
template <class K, class V, class... R>
void put(std::string& o, const std::unordered_map<K, V, R...>& v, bool& tr) { put_map(o, v, tr); }

template <class S>
void put_set(std::string& o, const S& s, bool& tr) {
    std::vector<typename S::key_type> items(s.begin(), s.end());
    std::sort(items.begin(), items.end());
    put_seq(o, (long long)items.size(), [&](long long i) { put(o, items[i], tr); }, tr);
}
template <class K, class... R>
void put(std::string& o, const std::set<K, R...>& v, bool& tr) { put_set(o, v, tr); }
template <class K, class... R>
void put(std::string& o, const std::multiset<K, R...>& v, bool& tr) { put_set(o, v, tr); }
template <class K, class... R>
void put(std::string& o, const std::unordered_set<K, R...>& v, bool& tr) { put_set(o, v, tr); }

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
            else if (cur.rfind("CPE_ARR2(", 0) == 0) cur = cur.substr(9, cur.find(',') - 9);
            else if (cur.rfind("CPE_ARRV(", 0) == 0) cur = cur.substr(9, cur.find(',') - 9);
            else if (cur.rfind("CPE_FLD(", 0) == 0) {   // "CPE_FLD(p, s)" -> "p.s"
                std::string in = cur.substr(8, cur.rfind(')') - 8), a = in.substr(0, in.find(',')), b = in.substr(in.find(',') + 1);
                auto trim = [](std::string x) { size_t l = x.find_first_not_of(' '), r = x.find_last_not_of(' '); return l == std::string::npos ? std::string() : x.substr(l, r - l + 1); };
                cur = trim(a) + "." + trim(b);
            }
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
#define CPE_ARRV(ptr, len) ::cpe_trace::arrv((ptr), (long long)(len))
#define CPE_ARR2(ptr, r, c) ::cpe_trace::arr2(&(ptr)[0][0], (long long)(r), (long long)(c))
#define CPE_FLD(vec, f) ::cpe_trace::fld((vec), [](const auto& e_) { return e_.f; })
#define CPE_SNAP(id, ...) ::cpe_trace::snap((id), #__VA_ARGS__, __VA_ARGS__)
