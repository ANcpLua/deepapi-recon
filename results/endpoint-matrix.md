# Endpoint matrix — 53 unique operations (raw analyzer output, grouped)

| Capability family | Ops | Endpoints |
|---|---:|---|
| **Scrape** | 27 | `POST /v1/scrape/github` <br> `POST /v1/scrape/github/commits` <br> `POST /v1/scrape/github/contents` <br> `POST /v1/scrape/github/issues` <br> `POST /v1/scrape/github/profile` · ≤$0.03 <br> `POST /v1/scrape/github/pulls` <br> `POST /v1/scrape/github/repo` <br> `POST /v1/scrape/github/search` <br> `POST /v1/scrape/instagram/comments` <br> `POST /v1/scrape/instagram/posts` <br> `POST /v1/scrape/instagram/profile` <br> `POST /v1/scrape/linkedin` <br> `POST /v1/scrape/linkedin/company` <br> `POST /v1/scrape/linkedin/jobs` <br> `POST /v1/scrape/linkedin/people` <br> `POST /v1/scrape/linkedin/posts` <br> `POST /v1/scrape/linkedin/profile` · ≤$0.05 <br> `POST /v1/scrape/pdf` <br> `POST /v1/scrape/twitter` <br> `POST /v1/scrape/twitter/replies` <br> `POST /v1/scrape/twitter/search` · ≤$0.03 <br> `POST /v1/scrape/twitter/user` <br> `POST /v1/scrape/website` · ≤$1.00 <br> `POST /v1/scrape/youtube/channel` <br> `POST /v1/scrape/youtube/search` <br> `POST /v1/scrape/youtube/shorts` <br> `POST /v1/scrape/youtube/transcript` · ≤$0.05 |
| **Search** | 1 | `POST /v1/search/web` · ≤$0.05 |
| **Research** | 1 | `POST /v1/research/deep` · ≤$0.10 |
| **Generate** | 1 | `POST /v1/generate/image` · ≤$0.20 |
| **Email** | 10 | `GET /v1/email/domains` <br> `POST /v1/email/domains` <br> `DELETE /v1/email/domains/{domainId}` <br> `POST /v1/email/domains/{domainId}/verify` <br> `GET /v1/email/drafts` <br> `POST /v1/email/drafts/{draftId}/send` <br> `GET /v1/email/identities` <br> `POST /v1/email/identities` <br> `GET /v1/email/messages` <br> `POST /v1/email/send` |
| **Memory** | 4 | `GET /v1/memory` <br> `DELETE /v1/memory/{path}` <br> `GET /v1/memory/{path}` <br> `POST /v1/memory/{path}` |
| **X (Twitter) actions** | 2 | `GET /v1/x/connection` <br> `POST /v1/x/post` |
| **Deploy** | 1 | `POST /v1/deploy` |
| **Requests** | 2 | `GET /v1/requests` <br> `GET /v1/requests/{requestId}` |
| **Account** | 3 | `GET /v1/balance` <br> `GET /v1/me` <br> `GET /v1/usage` |
| **Health** | 1 | `GET /v1/health` |