# blunderfixer-api

## Archive a drill

To hide a drill from your feed, send a `PATCH` request to `/drills/{id}` with
`{"archived": true}`. The endpoint returns the updated drill information.

## View recently drilled

Pass `recent_first=true` to `/drills` to sort results by most recently
drilled positions first. By default, drills are ordered oldest first so
that never-practiced items appear at the top of the feed.

### Recently played drills

To fetch only drills you've played recently, call `GET /drills/recent` with
`username` and an optional `limit` (defaults to 20). Results are ordered by
`last_drilled_at` descending and exclude archived drills unless
`include_archived=true` is provided.
