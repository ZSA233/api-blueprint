# packet AuditPacket

```yaml
endian: little
content-type: application/octet-stream
```

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| kind | Kind | 1 | const=2 | packet kind |
| flags | Flags | 1 | min=0 | audit flags |
| item_count | u16 | 1 | min=1,max=4,sizeof=items | item count |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| items | Item | item_count | | audit items |
| checksum | u32 | 1 | assert=item_count | simple checksum |

## struct Item

| field | type | count | rule | comment |
|---|---|---:|---|---|
| id | u32 | 1 | min=1 | audit item id |
| code | u16 | 1 | min=1,max=999 | audit code |

## enum Kind : u16

| name | value | comment |
|---|---:|---|
| Metric | 1 | metric packet |
| Audit | 2 | audit packet |

## bitflags Flags : u32

| name | bits | rule | comment |
|---|---:|---|---|
| HasItems | 0 | | items are present |
| Mode | 1..2 | enum=Kind | packet mode |
| Reserved | 3..31 | const=0 | reserved bits must be zero |
