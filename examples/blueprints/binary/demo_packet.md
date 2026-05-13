# packet DemoPacket

endian: little
content-type: application/octet-stream
content-encoding: identity,gzip

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| magic | bytes | 4 | const="ABP1" | magic |
| version | u16 | 1 | const=1 | protocol version |
| kind | DemoKind | 1 | const=1 | packet kind |
| flags | DemoFlags | 1 | min=0 | feature flags |
| header_pad | padding | 1 | | alignment padding |
| reserved0 | reserved | 2 | | reserved zero bytes |
| short_code | u24 | 1 | min=1,max=16777215 | 24-bit unsigned code |
| signed_delta | i24 | 1 | min=0,max=8388607 | 24-bit signed delta |
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

## enum DemoKind : u16

| name | value | comment |
|---|---:|---|
| Metric | 1 | metric packet |
| Debug | 2 | debug packet |

## bitflags DemoFlags : u32

| name | bits | rule | comment |
|---|---:|---|---|
| HasPayload | 0 | | payload is present |
| HasScores | 1 | | scores are present |
| FastPath | 2 | | fast path marker |
| Mode | 3..4 | enum=DemoKind | packet mode |
| Reserved | 5..31 | const=0 | reserved bits must be zero |
