# Apple M1 Max / 64GB / 24 GPU cores

**Model:** mlx-community/qwen3.5-35b-a3b  
**Backend:** lmstudio  
**Scenario:** doc-summary (single-shot)  

| Turn | Context | Prefill | Gen | Gen tok/s | Effective tok/s | Total | Output |
|-----:|--------:|--------:|----:|----------:|----------------:|------:|-------:|
| 1 | 425 | 5.57s | 2.16s | 57.5 | **16.0** | 7.73s | 124 |
| 2 | 612 | 5.66s | 1.66s | 56.2 | **12.7** | 7.31s | 93 |
| 3 | 535 | 5.79s | 2.02s | 56.9 | **14.7** | 7.81s | 115 |
| 4 | 524 | 5.79s | 1.73s | 56.8 | **13.0** | 7.51s | 98 |
| 5 | 1,518 | 8.54s | 2.06s | 56.8 | **11.0** | 10.60s | 117 |

**Total prefill:** 31.3s  
**Total generation:** 9.6s  
**Total time:** 41.0s  
**Avg generation tok/s:** 56.8  
**Avg effective tok/s:** 13.4  
