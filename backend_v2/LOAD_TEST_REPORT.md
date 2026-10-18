# Docker yük / RAM testi

Bu dosya araç tarafından üretilmiştir. Geçerli AI girdisi ve /health/deep kullanılmadı. POST gövdesi yalnızca `{}`; 422 ve 429 kontrollü retlerdir. 503 LOW_MEMORY ayrıca 5xx sayısında gösterilir; kapasite başarısı değildir.

En fazla 72 istek, 4 eşzamanlı istek, istek başına 3s timeout; 60s yük kabul bütçesi (son dalga ve Docker ölçümleri ek süre alabilir). RAM >=320 MiB olduğunda yeni yük durur; bu örneklemeli bir korumadır, OOM olmayacağı garantisi değildir. cgroup current container belleğidir (RSS değildir); örneklenmiş maksimum alt sınırdır. cgroup peak container ömrüne aittir, yalnızca bu teste ait değildir. Ölçüm docker exec Python sürecinin küçük ek maliyetini içerir.

BUSY/RATE_LIMITED yalnızca hata kodu sayımlarında gözlenirse raporlanır; gözlenmemesi limitlerin doğrulandığı anlamına gelmez. Kota pencere sınırları ve önceki trafik sonuçları etkiler; araç Retry-After bekleyip yeniden denemez veya kota aşmaz. Gerçek AI, SSE akışı, uzun işlem kapasitesi, OOM ve bellek sızıntısı test edilmedi.

RAM MiB: önce=68.23, örneklenen maksimum=69.39, sonra=69.08. Container ömrü tepe MiB: 71.1875.

Gecikmeler istemci uçtan uca süreleridir; p50/p95 nearest-rank ile hesaplanır.

```json
{
  "timestamp_utc": "2026-10-18T13:38:10.643261+00:00",
  "url": "http://127.0.0.1:18001",
  "container": "verifia-health-test",
  "docker": {
    "image": "verifia-backend-healthcheck",
    "memory_limit_bytes": 536870912,
    "health_before": "healthy",
    "ram_samples": [
      {
        "current": 71544832,
        "peak": 74645504
      },
      {
        "current": 72491008,
        "peak": 74645504
      },
      {
        "current": 72765440,
        "peak": 74645504
      },
      {
        "current": 68730880,
        "peak": 74645504
      },
      {
        "current": 72630272,
        "peak": 74645504
      },
      {
        "current": 72359936,
        "peak": 74645504
      },
      {
        "current": 68673536,
        "peak": 74645504
      },
      {
        "current": 72433664,
        "peak": 74645504
      }
    ],
    "monitor_errors": [],
    "health_after": "healthy",
    "oom_killed_after": false,
    "running_after": true
  },
  "phases": [
    {
      "concurrency": 1,
      "wall_s": 2.507,
      "throughput_rps": 9.573,
      "endpoints": {
        "/": {
          "requests": 6,
          "http": {
            "200": 6
          },
          "errors": {},
          "retry_after": {},
          "transport_errors": 0,
          "http_5xx": 0,
          "http_4xx": 0,
          "transport_error_rate_pct": 0.0,
          "http_5xx_rate_pct": 0.0,
          "http_4xx_rate_pct": 0.0,
          "unexpected_rate_pct": 0.0,
          "p50_ms": 45.777,
          "p95_ms": 48.771,
          "max_ms": 48.771
        },
        "/health": {
          "requests": 6,
          "http": {
            "200": 6
          },
          "errors": {},
          "retry_after": {},
          "transport_errors": 0,
          "http_5xx": 0,
          "http_4xx": 0,
          "transport_error_rate_pct": 0.0,
          "http_5xx_rate_pct": 0.0,
          "http_4xx_rate_pct": 0.0,
          "unexpected_rate_pct": 0.0,
          "p50_ms": 42.155,
          "p95_ms": 46.112,
          "max_ms": 46.112
        },
        "/verify": {
          "requests": 6,
          "http": {
            "422": 5,
            "429": 1
          },
          "errors": {
            "VALIDATION_ERROR": 5,
            "RATE_LIMITED": 1
          },
          "retry_after": {
            "55": 1
          },
          "transport_errors": 0,
          "http_5xx": 0,
          "http_4xx": 6,
          "transport_error_rate_pct": 0.0,
          "http_5xx_rate_pct": 0.0,
          "http_4xx_rate_pct": 100.0,
          "unexpected_rate_pct": 0.0,
          "p50_ms": 45.278,
          "p95_ms": 48.801,
          "max_ms": 48.801
        },
        "/verify/stream": {
          "requests": 6,
          "http": {
            "422": 5,
            "429": 1
          },
          "errors": {
            "VALIDATION_ERROR": 5,
            "RATE_LIMITED": 1
          },
          "retry_after": {
            "55": 1
          },
          "transport_errors": 0,
          "http_5xx": 0,
          "http_4xx": 6,
          "transport_error_rate_pct": 0.0,
          "http_5xx_rate_pct": 0.0,
          "http_4xx_rate_pct": 100.0,
          "unexpected_rate_pct": 0.0,
          "p50_ms": 44.371,
          "p95_ms": 47.924,
          "max_ms": 47.924
        }
      }
    },
    {
      "concurrency": 2,
      "wall_s": 2.37,
      "throughput_rps": 10.128,
      "endpoints": {
        "/": {
          "requests": 6,
          "http": {
            "200": 6
          },
          "errors": {},
          "retry_after": {},
          "transport_errors": 0,
          "http_5xx": 0,
          "http_4xx": 0,
          "transport_error_rate_pct": 0.0,
          "http_5xx_rate_pct": 0.0,
          "http_4xx_rate_pct": 0.0,
          "unexpected_rate_pct": 0.0,
          "p50_ms": 65.905,
          "p95_ms": 72.623,
          "max_ms": 72.623
        },
        "/health": {
          "requests": 6,
          "http": {
            "200": 6
          },
          "errors": {},
          "retry_after": {},
          "transport_errors": 0,
          "http_5xx": 0,
          "http_4xx": 0,
          "transport_error_rate_pct": 0.0,
          "http_5xx_rate_pct": 0.0,
          "http_4xx_rate_pct": 0.0,
          "unexpected_rate_pct": 0.0,
          "p50_ms": 70.24,
          "p95_ms": 81.636,
          "max_ms": 81.636
        },
        "/verify": {
          "requests": 6,
          "http": {
            "429": 6
          },
          "errors": {
            "RATE_LIMITED": 6
          },
          "retry_after": {
            "55": 1,
            "54": 3,
            "53": 2
          },
          "transport_errors": 0,
          "http_5xx": 0,
          "http_4xx": 6,
          "transport_error_rate_pct": 0.0,
          "http_5xx_rate_pct": 0.0,
          "http_4xx_rate_pct": 100.0,
          "unexpected_rate_pct": 0.0,
          "p50_ms": 66.448,
          "p95_ms": 91.576,
          "max_ms": 91.576
        },
        "/verify/stream": {
          "requests": 6,
          "http": {
            "429": 6
          },
          "errors": {
            "RATE_LIMITED": 6
          },
          "retry_after": {
            "55": 1,
            "54": 3,
            "53": 2
          },
          "transport_errors": 0,
          "http_5xx": 0,
          "http_4xx": 6,
          "transport_error_rate_pct": 0.0,
          "http_5xx_rate_pct": 0.0,
          "http_4xx_rate_pct": 100.0,
          "unexpected_rate_pct": 0.0,
          "p50_ms": 67.48,
          "p95_ms": 94.368,
          "max_ms": 94.368
        }
      }
    },
    {
      "concurrency": 4,
      "wall_s": 2.361,
      "throughput_rps": 10.166,
      "endpoints": {
        "/": {
          "requests": 6,
          "http": {
            "200": 6
          },
          "errors": {},
          "retry_after": {},
          "transport_errors": 0,
          "http_5xx": 0,
          "http_4xx": 0,
          "transport_error_rate_pct": 0.0,
          "http_5xx_rate_pct": 0.0,
          "http_4xx_rate_pct": 0.0,
          "unexpected_rate_pct": 0.0,
          "p50_ms": 134.623,
          "p95_ms": 151.268,
          "max_ms": 151.268
        },
        "/health": {
          "requests": 6,
          "http": {
            "200": 6
          },
          "errors": {},
          "retry_after": {},
          "transport_errors": 0,
          "http_5xx": 0,
          "http_4xx": 0,
          "transport_error_rate_pct": 0.0,
          "http_5xx_rate_pct": 0.0,
          "http_4xx_rate_pct": 0.0,
          "unexpected_rate_pct": 0.0,
          "p50_ms": 136.543,
          "p95_ms": 151.848,
          "max_ms": 151.848
        },
        "/verify": {
          "requests": 6,
          "http": {
            "429": 6
          },
          "errors": {
            "RATE_LIMITED": 6
          },
          "retry_after": {
            "52": 3,
            "51": 2,
            "50": 1
          },
          "transport_errors": 0,
          "http_5xx": 0,
          "http_4xx": 6,
          "transport_error_rate_pct": 0.0,
          "http_5xx_rate_pct": 0.0,
          "http_4xx_rate_pct": 100.0,
          "unexpected_rate_pct": 0.0,
          "p50_ms": 134.018,
          "p95_ms": 136.758,
          "max_ms": 136.758
        },
        "/verify/stream": {
          "requests": 6,
          "http": {
            "429": 6
          },
          "errors": {
            "RATE_LIMITED": 6
          },
          "retry_after": {
            "52": 3,
            "51": 2,
            "50": 1
          },
          "transport_errors": 0,
          "http_5xx": 0,
          "http_4xx": 6,
          "transport_error_rate_pct": 0.0,
          "http_5xx_rate_pct": 0.0,
          "http_4xx_rate_pct": 100.0,
          "unexpected_rate_pct": 0.0,
          "p50_ms": 131.668,
          "p95_ms": 135.379,
          "max_ms": 135.379
        }
      }
    }
  ],
  "notes": []
}
```
