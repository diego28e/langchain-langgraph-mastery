# Orbita Cloud technical FAQ

## Station data is not syncing

Stations upload readings every 5 minutes. If the dashboard shows no new data, check that the station is online, that its firmware is 2.4 or newer, and that the station clock is correct. A sync delay of up to 15 minutes is normal during maintenance windows.

## API errors and rate limits

The REST API allows 600 requests per minute on Pro and 3000 on Team. A 429 Too Many Requests error means you hit the rate limit: wait for the number of seconds in the Retry-After header, then retry with exponential backoff. A 401 error means the API key is missing, revoked or sent in the wrong header; send it as `Authorization: Bearer <key>`.

## Webhooks

Webhooks are retried 5 times over 24 hours when your endpoint does not answer with a 2xx status. Each delivery carries an `Orbita-Signature` header that you should verify with your signing secret.

## Exporting data

You can export readings as CSV or Parquet from Data → Export. Exports larger than 1 GB are prepared in the background and emailed as a download link that expires after 7 days.

## Service status

The live service status is published at status.orbita.example. During an incident the dashboard may show stale charts, but readings are buffered on the station for up to 72 hours and uploaded when the service recovers.
