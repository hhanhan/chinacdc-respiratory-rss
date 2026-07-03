# China CDC Respiratory Sentinel RSS

This repository generates an RSS feed for the China CDC column:

https://www.chinacdc.cn/jksj/jksj04_14275/

The feed tracks weekly posts titled `全国急性呼吸道传染病哨点监测情况`.

## RSS

After GitHub Pages is enabled, subscribe to:

```text
https://hhanhan.github.io/chinacdc-respiratory-rss/chinacdc-respiratory-sentinel.xml
```

## Update

The GitHub Actions workflow runs every Friday at 10:30 and 20:30 Beijing time.

Manual update:

```bash
python scripts/chinacdc_respiratory_rss.py --output docs/chinacdc-respiratory-sentinel.xml
```
