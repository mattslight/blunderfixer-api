# blunderfixer-api

## Drills Endpoint

`GET /drills` lists practice positions for a given user. By default the
response hides drills that have been **archived** or **mastered** (defined as
five consecutive `pass` results). To include either category you can pass an
`include` query parameter containing one or both of `archived` and `mastered`:

```
/drills?username=alice&include=archived&include=mastered
```

Each drill in the response exposes two boolean fields:

- `archived` – set when the user chooses “don’t show me again”.
- `mastered` – true when the five most recent history entries are all passes.
