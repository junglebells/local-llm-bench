# Apple M1 Max / 64GB / 24 GPU cores

**Model:** mlx-community/qwen3.5-35b-a3b  
**Backend:** lmstudio  
**Scenario:** creative-writing (single-shot)  

| Turn | Context | Prefill | Gen | Gen tok/s | Effective tok/s | Total | Output |
|-----:|--------:|--------:|----:|----------:|----------------:|------:|-------:|
| 1 | 57 | 4.65s | 7.16s | 59.1 | **35.8** | 11.81s | 423 |
| 2 | 60 | 4.39s | 11.58s | 58.5 | **42.4** | 15.97s | 677 |
| 3 | 58 | 4.41s | 6.34s | 59.2 | **34.9** | 10.75s | 375 |

**Total prefill:** 13.4s  
**Total generation:** 25.1s  
**Total time:** 38.5s  
**Avg generation tok/s:** 58.9  
**Avg effective tok/s:** 38.3  
