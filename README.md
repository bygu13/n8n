# Dainuie – Telegram social media manager for n8n

An n8n automation that lets you run the **dainuie.online** social accounts from a Telegram chat.
You message the bot in plain language (Romanian or English), and it:

- talks back and forth with you to understand what you want to post,
- writes and curates the copy, one tailored version per platform (Facebook, Instagram, TikTok),
- generates an AI image and, where a platform needs it (TikTok, Instagram Reels), an AI video,
- shows you previews on Telegram and waits for your approval,
- publishes to the Facebook Page, the Instagram business account and TikTok, then sends you a results card with links.

Nothing is ever published without your explicit "post it".

## What is in this repo

| File | Purpose |
| --- | --- |
| `workflows/01-dainuie-telegram-social-manager.json` | Main workflow. Telegram trigger, authorization check, photo intake, the AI agent (Claude), memory, and the three tools below. |
| `workflows/02-dainuie-generate-image.json` | Tool sub-workflow. OpenAI `gpt-image-1` → Cloudinary (public URL) → Telegram preview. Returns `image_url`. |
| `workflows/03-dainuie-generate-video.json` | Tool sub-workflow. fal.ai text-to-video (Kling 2.1 by default, 9:16) → polling → Cloudinary → Telegram preview. Returns `video_url`. |
| `workflows/04-dainuie-publish-post.json` | Tool sub-workflow. Publishes to Facebook (text/photo/video), Instagram (image or Reel, with container polling) and TikTok (token refresh, single-chunk upload, status polling). Sends a results card. |
| `scripts/import.sh` | Imports all four workflows with the n8n CLI, keeping their ids linked. |
| `scripts/build_publish_workflow.py` | Generates workflow 04. Edit and re-run it if you want to change the publishing logic. |

## How a conversation works

```
You:  Vreau să postez despre noua colecție de toamnă, pe toate conturile.
Bot:  asks 1-2 questions if needed, then shows Facebook / Instagram / TikTok drafts
You:  ok, but shorter on Instagram
Bot:  revised drafts + proposes a visual concept
You:  da, generează imaginea și un video pentru TikTok
Bot:  (calls generate_image → you receive the image preview)
      (calls generate_video → you receive the video preview, 1-4 minutes)
You:  perfect, postează
Bot:  (calls publish_post once) → you receive "📣 Publishing results" with links
```

You can also **send a photo with a caption**. The photo is uploaded to Cloudinary and the agent uses it as the post image instead of generating one.

## Architecture

```
Telegram ──► Telegram Trigger ─► Config ─► Is Authorized? ─► Message Type
                                                              ├─ photo ─► download ─► Cloudinary ─┐
                                                              └─ text ────────────────────────────┴─► Social Media Agent ─► Format ─► Send Reply
                                                                                                        │  Claude (Anthropic) · window memory per chat
                                                                                                        ├─ tool: generate_image  → workflow 02
                                                                                                        ├─ tool: generate_video  → workflow 03
                                                                                                        └─ tool: publish_post    → workflow 04
```

Workflow 04 fans out one work item per platform through a *Loop Over Items* node, so one failing platform never blocks the others. Every external call has its error output wired to a `… Failed` node, and the final card lists each platform as ✅ or ❌ with the reason.

## Setup

### 1. Accounts and credentials you need

| Service | Why | n8n credential type |
| --- | --- | --- |
| Telegram bot (via @BotFather) | Chat interface | **Telegram API** |
| Anthropic API key | The agent's brain (`claude-opus-5`) | **Anthropic** |
| OpenAI API key | Image generation (`gpt-image-1`) | **OpenAI** |
| fal.ai API key | Video generation | **Header Auth**: name `Authorization`, value `Key <FAL_KEY>` |
| Cloudinary (free tier is fine) | Public URLs for images/videos. Meta and TikTok only accept publicly reachable media. | none – uses an *unsigned upload preset* |
| Meta app + Facebook Page + Instagram business account | Publishing to Facebook and Instagram | **Facebook Graph API** (a long-lived *Page* access token) |
| TikTok for Developers app with Content Posting API | Publishing to TikTok | none – client key/secret + refresh token go in the Config node |

**Meta token scopes**: `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`, `instagram_basic`, `instagram_content_publish`. Use a long-lived Page token (generate from a long-lived user token via `/{page-id}?fields=access_token`). The Instagram account must be a Business/Creator account linked to the Page. Get the IG user id from `/{page-id}?fields=instagram_business_account`.

**TikTok**: enable *Login Kit* and *Content Posting API*, request scopes `user.info.basic`, `video.upload`, `video.publish`. Complete the OAuth flow once (any OAuth playground or a one-off n8n workflow works) and copy the `refresh_token`. Until TikTok has audited your app, posts can only be `SELF_ONLY` (private); switch `TIKTOK_PRIVACY_LEVEL` to `PUBLIC_TO_EVERYONE` after approval. The refresh token is stored in workflow static data after the first successful refresh, so it keeps working even if TikTok rotates it.

**Cloudinary**: Settings → Upload → *Add upload preset* → Signing mode **Unsigned**. Note the cloud name and the preset name.

### 2. Import the workflows

Option A – n8n CLI (recommended, keeps the ids linked):

```sh
sh scripts/import.sh            # or: n8n import:workflow --separate --input=./workflows
```

Option B – n8n UI: import each JSON file with *Workflows → Import from File*. The UI assigns new ids, so afterwards open the main workflow, open each of the three tool nodes (`generate_image`, `generate_video`, `publish_post`) and re-select the matching sub-workflow from the list.

### 3. Fill in the Config nodes

Every value that starts with `REPLACE` must be changed.

| Workflow | Config field | Value |
| --- | --- | --- |
| 01 | `ALLOWED_CHAT_ID` | Your Telegram chat id. Message the bot once before setting it; the bot replies with your id. |
| 01 | `BRAND_DESCRIPTION` | What dainuie.online is, audience, tone. The agent writes better copy with this. |
| 01, 02, 03 | `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_UPLOAD_PRESET` | From Cloudinary. |
| 02, 03 | `BRAND_STYLE` | Visual style appended to every image/video prompt so posts look consistent. |
| 03 | `FAL_MODEL` | Default `fal-ai/kling-video/v2.1/standard/text-to-video`. Any fal.ai text-to-video model that takes `prompt`, `duration`, `aspect_ratio` works (e.g. a Veo 3 endpoint for audio). Check the response key in *Upload to Cloudinary* if you switch. |
| 04 | `FACEBOOK_PAGE_ID`, `INSTAGRAM_USER_ID` | From Meta. |
| 04 | `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REFRESH_TOKEN`, `TIKTOK_USERNAME`, `TIKTOK_PRIVACY_LEVEL` | From TikTok. |
| 04 | `GRAPH_API_VERSION` | `v23.0`. Bump when Meta deprecates it. |

Tip: for secrets you can use `{{ $env.TIKTOK_CLIENT_SECRET }}` in the Config node instead of a literal value (requires `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`).

### 4. Attach credentials

Open each workflow and pick the credential on the nodes that show a warning:

- 01: Telegram nodes → Telegram API; *Anthropic Chat Model* → Anthropic.
- 02: *Generate Image (OpenAI)* → OpenAI; *Preview on Telegram* → Telegram API.
- 03: *Submit Video Job*, *Check Status*, *Fetch Result* → the fal.ai Header Auth; *Preview on Telegram* → Telegram API.
- 04: all *FB …* and *IG …* HTTP nodes → Facebook Graph API; *Send Results Card* → Telegram API.

### 5. Activate

Activate **only** the main workflow (01). The three tool workflows are called by it and stay inactive. Send the bot a message.

## Customising

- **Tone / platform rules**: edit the system message in the *Social Media Agent* node.
- **Model**: change the model id in *Anthropic Chat Model* (`claude-opus-5` by default; `claude-sonnet-5` is cheaper).
- **Image style or size**: *Config* in workflow 02. The agent picks `square` for feed posts, `portrait` for stories.
- **Video length**: the agent passes `5` or `10` seconds. Cost depends on the fal.ai model.
- **Cross-posting the same video as an Instagram Reel**: already supported. If a `video_url` is present, the Instagram branch creates a `REELS` container.
- **Scheduled / recurring posting**: add a *Schedule Trigger* that calls workflow 04 directly with pre-written captions, or ask the bot and paste the result into a Data Table. Not included by default.

## Limits to know

- Telegram photo download is capped at 20 MB by Telegram; video previews sent by URL are capped at 20 MB.
- The TikTok branch uploads in a single chunk, which TikTok allows up to 64 MB. AI clips of 5–10 s are far below that.
- Instagram feed images must be between 4:5 and 1.91:1. Use `square` images for the feed; `portrait` (2:3) is for stories.
- Workflow static data (used for the TikTok refresh token) is only saved on production executions, not on manual test runs.
- Anthropic, OpenAI and fal.ai calls cost money per post. An image is a few cents, a 5 s Kling clip is roughly a quarter of a dollar; check current prices.
