# Apple M1 Max / 64GB / 24 GPU cores

**Model:** mlx-community/qwen3.5-35b-a3b  
**Backend:** lmstudio  
**Scenario:** prefill-test (single-shot)  

| Turn | Context | Prefill | Gen | Gen tok/s | Effective tok/s | Total | Output |
|-----:|--------:|--------:|----:|----------:|----------------:|------:|-------:|
| 1 | 655 | 6.87s | 1.89s | 59.4 | **12.8** | 8.75s | 112 |
| 2 | 1,453 | 9.23s | 2.53s | 56.5 | **12.2** | 11.77s | 143 |
| 3 | 3,015 | 14.99s | 2.60s | 50.4 | **7.4** | 17.59s | 131 |
| 4 | 8,496 | 49.41s | 2.87s | 51.2 | **2.8** | 52.28s | 147 |

**Total prefill:** 80.5s  
**Total generation:** 9.9s  
**Total time:** 90.4s  
**Avg generation tok/s:** 54.4  
**Avg effective tok/s:** 5.9  
