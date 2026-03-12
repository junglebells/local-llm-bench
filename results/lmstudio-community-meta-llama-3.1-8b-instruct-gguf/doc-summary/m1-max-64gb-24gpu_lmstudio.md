# Apple M1 Max / 64GB / 24 GPU cores

**Model:** lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF  
**Backend:** lmstudio  
**Scenario:** doc-summary (single-shot)  

| Turn | Context | Prefill | Gen | Gen tok/s | Effective tok/s | Total | Output |
|-----:|--------:|--------:|----:|----------:|----------------:|------:|-------:|
| 1 | 425 | 1.49s | 1.62s | 40.8 | **21.2** | 3.11s | 66 |
| 2 | 612 | 1.32s | 1.67s | 40.8 | **22.8** | 2.98s | 68 |
| 3 | 535 | 1.49s | 1.92s | 40.6 | **22.8** | 3.42s | 78 |
| 4 | 524 | 1.32s | 1.80s | 41.2 | **23.7** | 3.12s | 74 |
| 5 | 1,518 | 4.56s | 1.50s | 39.9 | **9.9** | 6.07s | 60 |

**Total prefill:** 10.2s  
**Total generation:** 8.5s  
**Total time:** 18.7s  
**Avg generation tok/s:** 40.7  
**Avg effective tok/s:** 18.5  
