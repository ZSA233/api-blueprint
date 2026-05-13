# packet DemoPacket

endian: little
content-type: application/octet-stream
content-encoding: identity,gzip

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| magic | bytes | 4 | const="ABP1" | magic |
| version | u16 | 1 | const=1 | protocol version |
| item_count | u16 | 1 | min=1,max=8,sizeof=items | item count |
| payload_len | u32 | 1 | min=0,max=64,sizeof=payload | payload bytes |
| score_count | u16 | 1 | const=2,max=4,sizeof=scores | score count |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| items | DemoPacketItem | item_count | | items |
| payload | bytes | payload_len | encoding=utf-8 | payload |
| scores | f64 | score_count | | scores |
| checksum | u32 | 1 | assert=item_count + payload_len | simple checksum |

## struct DemoPacketItem

| field | type | count | rule | comment |
|---|---|---:|---|---|
| id | u32 | 1 | min=1,max=999 | item id |
| enabled | bool | 1 | | enabled |
| value | f64 | 1 | | value |
| label_len | u8 | 1 | min=1,max=16,sizeof=label | label bytes |
| label | bytes | label_len | encoding=utf-8 | label |
