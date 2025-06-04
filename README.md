# blunderfixer-api

## Archive a drill

To hide a drill from your feed, send a `PATCH` request to `/drills/{id}` with
`{"archived": true}`. The endpoint returns the updated drill information.
