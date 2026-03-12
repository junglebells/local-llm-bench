# Apple M1 Max / 64GB / 24 GPU cores

**Model:** mlx-community/qwen3.5-35b-a3b  
**Backend:** lmstudio  
**Scenario:** ops-agent (conversation)  

| Turn | Context | Prefill | Gen | Gen tok/s | Effective tok/s | Total | Output |
|-----:|--------:|--------:|----:|----------:|----------------:|------:|-------:|
| 1 | 575 | 6.38s | 3.01s | 56.8 | **18.2** | 9.39s | 171 |
| 2 | 988 | 8.02s | 6.29s | 56.8 | **25.0** | 14.31s | 357 |
| 3 | 1,448 | 9.49s | 4.44s | 57.5 | **18.3** | 13.93s | 255 |
| 4 | 1,931 | 11.17s | 4.15s | 57.5 | **15.6** | 15.32s | 239 |
| 5 | 2,427 | 12.74s | 5.92s | 56.6 | **18.0** | 18.66s | 335 |
| 6 | 2,989 | 14.96s | 5.97s | 55.6 | **15.9** | 20.93s | 332 |
| 7 | 3,397 | 16.20s | 5.79s | 56.6 | **14.9** | 21.99s | 328 |
| 8 | 3,917 | 17.90s | 6.12s | 55.2 | **14.1** | 24.02s | 338 |

**Total prefill:** 96.9s  
**Total generation:** 41.7s  
**Total time:** 138.6s  
**Avg generation tok/s:** 56.6  
**Avg effective tok/s:** 17.0  
