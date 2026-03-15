// 氣泡排序法 (Bubble Sort)
// 原理：反覆比較相鄰元素，將較大的值往後推
#include <iostream>
using namespace std;

void bubbleSort(int arr[], int n) {
	for (int i = 0; i < n - 1; i++) {
		for (int j = 0; j < n - i - 1; j++) {
			if (arr[j] > arr[j + 1]) {
				int temp   = arr[j];
				arr[j]     = arr[j + 1];
				arr[j + 1] = temp;
			}
		}
	}
}

void printArray(int arr[], int n) {
	for (int i = 0; i < n; i++)
		cout << arr[i] << " ";
	cout << endl;
}

int main() {
	int arr[] = {64, 34, 25, 12, 22, 11, 90};
	int n = 7;

	cout << "排序前：";
	printArray(arr, n);
}
