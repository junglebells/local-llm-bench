# Apple M1 Max / 64GB / 24 GPU cores

**Model:** lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF  
**Backend:** lmstudio  
**Scenario:** creative-writing (single-shot)  

| Turn | Context | Prefill | Gen | Gen tok/s | Effective tok/s | Total | Output |
|-----:|--------:|--------:|----:|----------:|----------------:|------:|-------:|
| 1 | 57 | 0.32s | 10.16s | 39.2 | **38.0** | 10.48s | 398 |
| 2 | 60 | 0.35s | 15.60s | 39.0 | **38.1** | 15.94s | 608 |
| 3 | 58 | 0.21s | 9.95s | 39.1 | **38.3** | 10.16s | 389 |

**Total prefill:** 0.9s  
**Total generation:** 35.7s  
**Total time:** 36.6s  
**Avg generation tok/s:** 39.1  
**Avg effective tok/s:** 38.1  
