# Apple M1 Max / 64GB / 24 GPU cores

**Model:** lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF  
**Backend:** lmstudio  
**Scenario:** prefill-test (single-shot)  

| Turn | Context | Prefill | Gen | Gen tok/s | Effective tok/s | Total | Output |
|-----:|--------:|--------:|----:|----------:|----------------:|------:|-------:|
| 1 | 655 | 2.43s | 4.72s | 31.4 | **20.7** | 7.15s | 148 |
| 2 | 1,453 | 5.11s | 4.03s | 37.0 | **16.3** | 9.14s | 149 |
| 3 | 3,015 | 11.19s | 4.26s | 35.0 | **9.6** | 15.44s | 149 |
| 4 | 8,496 | 46.67s | 4.94s | 30.2 | **2.9** | 51.60s | 149 |

**Total prefill:** 65.4s  
**Total generation:** 17.9s  
**Total time:** 83.3s  
**Avg generation tok/s:** 33.4  
**Avg effective tok/s:** 7.1  
