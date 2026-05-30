# packet WidePacket

```yaml
endian: little
content-type: application/octet-stream
```

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| magic | bytes | 4 | const="WID1" | magic |
| payload_len | u64 | 1 | min=0,max=32,sizeof=payload | payload bytes |
| signed_wide | i64 | 1 | min=-5000000000,max=5000000000 | signed wide value |
| marker | u64 | 1 | const=9007199254740991 | max safe marker |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| payload | bytes | payload_len | encoding=utf-8 | payload |
| checksum | u64 | 1 | assert=payload_len | simple checksum |
