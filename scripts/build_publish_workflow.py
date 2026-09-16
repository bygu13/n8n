#!/usr/bin/env python3
"""Generates workflows/04-dainuie-publish-post.json.

Kept as a script because the workflow embeds several JavaScript Code nodes and
long expressions; generating from Python avoids hand-escaping them.
"""
import json
import pathlib

GRAPH = "https://graph.facebook.com/{{ $('Config').first().json.GRAPH_API_VERSION }}"
POST = "$('Loop Over Items').item.json"
CFG = "$('Config').first().json"

ERROR_EXPR = (
    "={{ (() => { const j = $json || {}; const e = j.error; "
    "if (e && !(typeof e === 'object' && e.code === 'ok')) { "
    "if (typeof e === 'string') return e; "
    "return [e.message, e.description, (e.code ? 'code ' + e.code : '')].filter(Boolean).join(' – ') || JSON.stringify(e); } "
    "if (j.data && j.data.fail_reason) return 'TikTok: ' + j.data.fail_reason + ' (status ' + j.data.status + ')'; "
    "if (j.data && j.data.status) return 'TikTok did not finish processing in time (status ' + j.data.status + ').'; "
    "if (j.status_code) return 'Instagram container status: ' + j.status_code + (j.status ? ' – ' + j.status : ''); "
    "return 'Timed out waiting for the platform to process the media.'; })() }}"
)

COND_OPTS = {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2}


def cond(cid, left, op_type, op, right="", single=False):
    operator = {"type": op_type, "operation": op}
    if single:
        operator["singleValue"] = True
    return {"id": cid, "leftValue": left, "rightValue": right, "operator": operator}


def conditions(*conds):
    return {"options": COND_OPTS, "conditions": list(conds), "combinator": "and"}


def node(name, ntype, version, pos, params, nid, **extra):
    n = {
        "parameters": params,
        "id": f"d4000000-0000-4000-8000-{nid:012d}",
        "name": name,
        "type": ntype,
        "typeVersion": version,
        "position": pos,
    }
    n.update(extra)
    return n


def set_node(name, pos, nid, assignments, include_other=False, **extra):
    return node(
        name,
        "n8n-nodes-base.set",
        3.4,
        pos,
        {
            "assignments": {
                "assignments": [
                    {"id": f"{nid}-{i}", "name": a[0], "value": a[1], "type": a[2]}
                    for i, a in enumerate(assignments)
                ]
            },
            **({"includeOtherFields": True} if include_other else {}),
            "options": {},
        },
        nid,
        **extra,
    )


def result_node(name, pos, nid, platform, link_expr):
    return set_node(
        name,
        pos,
        nid,
        [
            ("platform", platform, "string"),
            ("ok", "={{ true }}", "boolean"),
            ("link", link_expr, "string"),
            ("error", "", "string"),
        ],
    )


def failed_node(name, pos, nid, platform):
    return set_node(
        name,
        pos,
        nid,
        [
            ("platform", platform, "string"),
            ("ok", "={{ false }}", "boolean"),
            ("link", "", "string"),
            ("error", ERROR_EXPR, "string"),
        ],
    )


def graph_http(name, pos, nid, method, url, json_body=None, query=None, on_error="continueErrorOutput"):
    params = {
        "method": method,
        "url": url,
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "facebookGraphApi",
        "options": {"timeout": 120000},
    }
    if json_body is not None:
        params.update({"sendBody": True, "specifyBody": "json", "jsonBody": json_body})
    if query:
        params.update({"sendQuery": True, "queryParameters": {"parameters": [{"name": k, "value": v} for k, v in query]}})
    extra = {"onError": on_error} if on_error else {}
    return node(name, "n8n-nodes-base.httpRequest", 4.2, pos, params, nid, **extra)


def tiktok_http(name, pos, nid, url, json_body, on_error="continueErrorOutput"):
    params = {
        "method": "POST",
        "url": url,
        "sendHeaders": True,
        "headerParameters": {
            "parameters": [
                {"name": "Authorization", "value": "=Bearer {{ $('Persist Tokens').item.json.access_token }}"},
                {"name": "Content-Type", "value": "application/json; charset=UTF-8"},
            ]
        },
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": json_body,
        "options": {"timeout": 120000},
    }
    return node(name, "n8n-nodes-base.httpRequest", 4.2, pos, params, nid, onError=on_error)


def if_node(name, pos, nid, *conds):
    return node(name, "n8n-nodes-base.if", 2.2, pos, {"conditions": conditions(*conds), "options": {}}, nid)


def wait_node(name, pos, nid, seconds, webhook_id):
    return node(name, "n8n-nodes-base.wait", 1.1, pos, {"amount": seconds, "unit": "seconds"}, nid, webhookId=webhook_id)


def code_node(name, pos, nid, code, on_error=None):
    extra = {"onError": on_error} if on_error else {}
    return node(name, "n8n-nodes-base.code", 2, pos, {"jsCode": code}, nid, **extra)


PLAN_CODE = r"""
// Expand the tool call into one work item per platform and validate it.
const input = $input.first().json;
const configured = (v) => typeof v === 'string' && v.trim() !== '' && !v.startsWith('REPLACE');
const isUrl = (u) => typeof u === 'string' && /^https?:\/\//i.test(u.trim());
const platforms = [...new Set(String(input.platforms || '')
  .toLowerCase().split(/[,\s;]+/).map((s) => s.trim()).filter(Boolean))];
const image_url = isUrl(input.image_url) ? input.image_url.trim() : '';
const video_url = isUrl(input.video_url) ? input.video_url.trim() : '';
const out = [];

if (platforms.length === 0) {
  out.push({ platform: 'none', caption: '', image_url, video_url,
    error: 'No platforms given. Expected a comma-separated list: facebook, instagram, tiktok.' });
}

for (const platform of platforms) {
  const item = { platform, caption: '', image_url, video_url, error: '' };
  if (platform === 'facebook') {
    item.caption = String(input.caption_facebook || '').trim();
    if (!configured(input.FACEBOOK_PAGE_ID)) item.error = 'FACEBOOK_PAGE_ID is not set in the Config node of the publish workflow.';
    else if (!item.caption && !image_url && !video_url) item.error = 'Facebook post has neither text nor media.';
  } else if (platform === 'instagram') {
    item.caption = String(input.caption_instagram || '').trim().slice(0, 2200);
    if (!configured(input.INSTAGRAM_USER_ID)) item.error = 'INSTAGRAM_USER_ID is not set in the Config node of the publish workflow.';
    else if (!image_url && !video_url) item.error = 'Instagram needs an image_url or a video_url.';
  } else if (platform === 'tiktok') {
    item.caption = String(input.caption_tiktok || '').trim().slice(0, 2200);
    if (!configured(input.TIKTOK_CLIENT_KEY) || !configured(input.TIKTOK_CLIENT_SECRET)) item.error = 'TikTok client key/secret are not set in the Config node of the publish workflow.';
    else if (!video_url) item.error = 'TikTok needs a video_url. Generate a video first.';
  } else {
    item.error = `Unknown platform "${platform}". Use facebook, instagram or tiktok.`;
  }
  out.push(item);
}

return out.map((json) => ({ json, pairedItem: { item: 0 } }));
""".strip()

RESOLVE_TOKEN_CODE = r"""
// TikTok access tokens live 24h. We refresh before every post and remember the
// latest refresh token in workflow static data (falls back to the Config seed).
const sd = $getWorkflowStaticData('global');
const cfg = $('Config').first().json;
const refreshToken = sd.tiktokRefreshToken || cfg.TIKTOK_REFRESH_TOKEN;
if (!refreshToken || String(refreshToken).startsWith('REPLACE')) {
  throw new Error('No TikTok refresh token. Complete the TikTok OAuth flow once and paste the refresh_token into TIKTOK_REFRESH_TOKEN in the Config node.');
}
return [{ json: { refresh_token: refreshToken }, pairedItem: { item: 0 } }];
""".strip()

PERSIST_TOKEN_CODE = r"""
const sd = $getWorkflowStaticData('global');
const r = $input.first().json;
if (!r.access_token) {
  throw new Error('TikTok token refresh failed: ' + (r.error_description || r.error || JSON.stringify(r)));
}
if (r.refresh_token) sd.tiktokRefreshToken = r.refresh_token;
return [{ json: { access_token: r.access_token, open_id: r.open_id }, pairedItem: { item: 0 } }];
""".strip()

MEASURE_CODE = r"""
// TikTok's init call needs the exact byte size; a single chunk is fine up to 64 MB.
const item = $input.first();
if (!item.binary || !item.binary.data) throw new Error('Video download returned no file.');
const buffer = await this.helpers.getBinaryDataBuffer(0, 'data');
if (buffer.length > 64 * 1024 * 1024) throw new Error('Video is larger than 64 MB; single-chunk TikTok upload is not possible.');
return [{ json: { video_size: buffer.length }, binary: item.binary, pairedItem: { item: 0 } }];
""".strip()

REATTACH_CODE = r"""
// Validate the init response and put the video bytes back on the item for the PUT upload.
const init = $input.first().json;
if (init.error && init.error.code && init.error.code !== 'ok') {
  throw new Error('TikTok init failed: ' + init.error.code + ' – ' + (init.error.message || ''));
}
if (!init.data || !init.data.upload_url) throw new Error('TikTok init returned no upload_url: ' + JSON.stringify(init));
const measured = $('Measure Video').first();
return [{
  json: { publish_id: init.data.publish_id, upload_url: init.data.upload_url, video_size: measured.json.video_size },
  binary: measured.binary,
  pairedItem: { item: 0 },
}];
""".strip()

SUMMARY_CODE = r"""
const results = $input.all().map((i) => i.json);
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const label = { facebook: 'Facebook', instagram: 'Instagram', tiktok: 'TikTok' };
const html = results.map((r) => {
  const name = esc(label[r.platform] || r.platform);
  if (r.ok) return `✅ <b>${name}</b>: ${r.link ? `<a href="${esc(r.link)}">open post</a>` : 'published'}`;
  return `❌ <b>${name}</b>: ${esc(r.error || 'unknown error')}`;
});
const text = results.map((r) => `${r.ok ? 'OK' : 'FAILED'} ${r.platform}: ${r.ok ? (r.link || 'published') : r.error}`);
const ok = results.filter((r) => r.ok).length;
return [{ json: {
  results,
  ok_count: ok,
  failed_count: results.length - ok,
  summary_text: text.join('\n'),
  summary_html: html.join('\n'),
} }];
""".strip()

nodes = []
nid = 0


def add(n):
    nodes.append(n)
    return n["name"]


# --- entry -----------------------------------------------------------------
nid += 1
add(node("Start", "n8n-nodes-base.executeWorkflowTrigger", 1.1, [0, 500], {
    "workflowInputs": {"values": [
        {"name": "platforms", "type": "string"},
        {"name": "caption_facebook", "type": "string"},
        {"name": "caption_instagram", "type": "string"},
        {"name": "caption_tiktok", "type": "string"},
        {"name": "image_url", "type": "string"},
        {"name": "video_url", "type": "string"},
        {"name": "chat_id", "type": "string"},
    ]}
}, nid))

nid += 1
add(set_node("Config", [220, 500], nid, [
    ("GRAPH_API_VERSION", "v23.0", "string"),
    ("FACEBOOK_PAGE_ID", "REPLACE_WITH_FACEBOOK_PAGE_ID", "string"),
    ("INSTAGRAM_USER_ID", "REPLACE_WITH_INSTAGRAM_BUSINESS_ACCOUNT_ID", "string"),
    ("TIKTOK_CLIENT_KEY", "REPLACE_WITH_TIKTOK_CLIENT_KEY", "string"),
    ("TIKTOK_CLIENT_SECRET", "REPLACE_WITH_TIKTOK_CLIENT_SECRET", "string"),
    ("TIKTOK_REFRESH_TOKEN", "REPLACE_WITH_TIKTOK_REFRESH_TOKEN", "string"),
    ("TIKTOK_PRIVACY_LEVEL", "SELF_ONLY", "string"),
    ("TIKTOK_USERNAME", "REPLACE_WITH_TIKTOK_HANDLE_WITHOUT_AT", "string"),
], include_other=True))

nid += 1
add(code_node("Plan Posts", [440, 500], nid, PLAN_CODE))

nid += 1
add(node("Loop Over Items", "n8n-nodes-base.splitInBatches", 3, [660, 500], {"batchSize": 1, "options": {}}, nid))

nid += 1
add(node("Route by Platform", "n8n-nodes-base.switch", 3.2, [900, 600], {
    "rules": {"values": [
        {"conditions": conditions(cond("s1", "={{ $json.error }}", "string", "notEmpty", single=True)), "renameOutput": True, "outputKey": "skipped"},
        {"conditions": conditions(cond("s2", "={{ $json.platform }}", "string", "equals", "facebook")), "renameOutput": True, "outputKey": "facebook"},
        {"conditions": conditions(cond("s3", "={{ $json.platform }}", "string", "equals", "instagram")), "renameOutput": True, "outputKey": "instagram"},
        {"conditions": conditions(cond("s4", "={{ $json.platform }}", "string", "equals", "tiktok")), "renameOutput": True, "outputKey": "tiktok"},
    ]},
    "options": {},
}, nid))

nid += 1
add(set_node("Skipped", [1140, 200], nid, [
    ("platform", "={{ $json.platform }}", "string"),
    ("ok", "={{ false }}", "boolean"),
    ("link", "", "string"),
    ("error", "={{ $json.error }}", "string"),
]))

# --- Facebook ---------------------------------------------------------------
nid += 1
add(node("FB Media Type", "n8n-nodes-base.switch", 3.2, [1140, 420], {
    "rules": {"values": [
        {"conditions": conditions(cond("f1", "={{ $json.video_url }}", "string", "notEmpty", single=True)), "renameOutput": True, "outputKey": "video"},
        {"conditions": conditions(cond("f2", "={{ $json.image_url }}", "string", "notEmpty", single=True)), "renameOutput": True, "outputKey": "image"},
    ]},
    "options": {"fallbackOutput": "extra"},
}, nid))

nid += 1
add(graph_http("FB Post Video", [1400, 300], nid, "POST",
               f"={GRAPH}/{{{{ {CFG}.FACEBOOK_PAGE_ID }}}}/videos",
               json_body=f"={{{{ {{ file_url: {POST}.video_url, description: {POST}.caption }} }}}}"))
nid += 1
add(graph_http("FB Post Photo", [1400, 440], nid, "POST",
               f"={GRAPH}/{{{{ {CFG}.FACEBOOK_PAGE_ID }}}}/photos",
               json_body=f"={{{{ {{ url: {POST}.image_url, message: {POST}.caption }} }}}}"))
nid += 1
add(graph_http("FB Post Text", [1400, 580], nid, "POST",
               f"={GRAPH}/{{{{ {CFG}.FACEBOOK_PAGE_ID }}}}/feed",
               json_body=f"={{{{ {{ message: {POST}.caption }} }}}}"))

FB_LINK = ("={{ $json.post_id ? 'https://www.facebook.com/' + $json.post_id "
           ": (String($json.id || '').includes('_') ? 'https://www.facebook.com/' + $json.id "
           f": 'https://www.facebook.com/' + {CFG}.FACEBOOK_PAGE_ID + '/videos/' + $json.id) }}}}")
nid += 1
add(result_node("FB Result", [1660, 380], nid, "facebook", FB_LINK))
nid += 1
add(failed_node("FB Failed", [1660, 560], nid, "facebook"))

# --- Instagram --------------------------------------------------------------
IG_BODY = (f"={{{{ {POST}.video_url "
           f"? {{ media_type: 'REELS', video_url: {POST}.video_url, caption: {POST}.caption, share_to_feed: true }} "
           f": {{ image_url: {POST}.image_url, caption: {POST}.caption }} }}}}")
nid += 1
add(graph_http("IG Create Container", [1140, 820], nid, "POST",
               f"={GRAPH}/{{{{ {CFG}.INSTAGRAM_USER_ID }}}}/media", json_body=IG_BODY))
nid += 1
add(wait_node("IG Wait 10s", [1360, 820], nid, 10, "dainuie-ig-wait"))
nid += 1
add(graph_http("IG Check Container", [1560, 820], nid, "GET",
               f"={GRAPH}/{{{{ $('IG Create Container').item.json.id }}}}",
               query=[("fields", "status_code,status")]))
nid += 1
add(if_node("IG Ready?", [1780, 820], nid, cond("ig1", "={{ $json.status_code }}", "string", "equals", "FINISHED")))
nid += 1
add(if_node("IG Failed or Timed Out?", [1780, 1020], nid,
            cond("ig2", "={{ ['ERROR', 'EXPIRED'].includes($json.status_code) || $runIndex >= 18 }}", "boolean", "true", single=True)))
nid += 1
add(graph_http("IG Publish", [2020, 760], nid, "POST",
               f"={GRAPH}/{{{{ {CFG}.INSTAGRAM_USER_ID }}}}/media_publish",
               json_body="={{ { creation_id: $('IG Create Container').item.json.id } }}"))
nid += 1
add(graph_http("IG Get Permalink", [2240, 760], nid, "GET",
               f"={GRAPH}/{{{{ $json.id }}}}", query=[("fields", "permalink")], on_error="continueRegularOutput"))
nid += 1
add(result_node("IG Result", [2460, 760], nid, "instagram",
                "={{ $json.permalink || ('https://www.instagram.com/ (media id ' + $('IG Publish').item.json.id + ')') }}"))
nid += 1
add(failed_node("IG Failed", [2240, 1020], nid, "instagram"))

# --- TikTok -----------------------------------------------------------------
nid += 1
add(code_node("Resolve Refresh Token", [1140, 1300], nid, RESOLVE_TOKEN_CODE, on_error="continueErrorOutput"))
nid += 1
add(node("Refresh TikTok Token", "n8n-nodes-base.httpRequest", 4.2, [1360, 1300], {
    "method": "POST",
    "url": "https://open.tiktokapis.com/v2/oauth/token/",
    "sendBody": True,
    "contentType": "form-urlencoded",
    "bodyParameters": {"parameters": [
        {"name": "client_key", "value": f"={{{{ {CFG}.TIKTOK_CLIENT_KEY }}}}"},
        {"name": "client_secret", "value": f"={{{{ {CFG}.TIKTOK_CLIENT_SECRET }}}}"},
        {"name": "grant_type", "value": "refresh_token"},
        {"name": "refresh_token", "value": "={{ $json.refresh_token }}"},
    ]},
    "options": {"timeout": 60000},
}, nid, onError="continueErrorOutput"))
nid += 1
add(code_node("Persist Tokens", [1580, 1300], nid, PERSIST_TOKEN_CODE, on_error="continueErrorOutput"))
nid += 1
add(node("Download Video", "n8n-nodes-base.httpRequest", 4.2, [1800, 1300], {
    "url": f"={{{{ {POST}.video_url }}}}",
    "options": {
        "timeout": 180000,
        "response": {"response": {"responseFormat": "file", "outputPropertyName": "data"}},
    },
}, nid, onError="continueErrorOutput"))
nid += 1
add(code_node("Measure Video", [2020, 1300], nid, MEASURE_CODE, on_error="continueErrorOutput"))

INIT_BODY = (f"={{{{ {{ post_info: {{ title: String({POST}.caption || '').slice(0, 2200), "
             f"privacy_level: {CFG}.TIKTOK_PRIVACY_LEVEL, disable_duet: false, disable_comment: false, disable_stitch: false, "
             "video_cover_timestamp_ms: 1000 }, "
             "source_info: { source: 'FILE_UPLOAD', video_size: $json.video_size, chunk_size: $json.video_size, total_chunk_count: 1 } } }}")
nid += 1
add(tiktok_http("TikTok Init Upload", [2240, 1300], nid, "https://open.tiktokapis.com/v2/post/publish/video/init/", INIT_BODY))
nid += 1
add(code_node("Reattach Video", [2460, 1300], nid, REATTACH_CODE, on_error="continueErrorOutput"))
nid += 1
add(node("TikTok Upload Bytes", "n8n-nodes-base.httpRequest", 4.2, [2680, 1300], {
    "method": "PUT",
    "url": "={{ $json.upload_url }}",
    "sendHeaders": True,
    "headerParameters": {"parameters": [
        {"name": "Content-Type", "value": "video/mp4"},
        {"name": "Content-Range", "value": "=bytes 0-{{ $json.video_size - 1 }}/{{ $json.video_size }}"},
    ]},
    "sendBody": True,
    "contentType": "binaryData",
    "inputDataFieldName": "data",
    "options": {"timeout": 300000},
}, nid, onError="continueErrorOutput"))
nid += 1
add(wait_node("TikTok Wait 15s", [2900, 1300], nid, 15, "dainuie-tiktok-wait"))
nid += 1
add(tiktok_http("TikTok Fetch Status", [3100, 1300], nid, "https://open.tiktokapis.com/v2/post/publish/status/fetch/",
                "={{ { publish_id: $('Reattach Video').item.json.publish_id } }}"))
nid += 1
add(if_node("TikTok Published?", [3320, 1300], nid,
            cond("tt1", "={{ $json.data && $json.data.status }}", "string", "equals", "PUBLISH_COMPLETE")))
nid += 1
add(if_node("TikTok Failed or Timed Out?", [3320, 1500], nid,
            cond("tt2", "={{ ($json.data && $json.data.status === 'FAILED') || $runIndex >= 24 }}", "boolean", "true", single=True)))
TT_LINK = ("={{ (($json.data || {}).publicaly_available_post_id || [])[0] "
           f"? 'https://www.tiktok.com/@' + {CFG}.TIKTOK_USERNAME + '/video/' + $json.data.publicaly_available_post_id[0] "
           f": 'https://www.tiktok.com/@' + {CFG}.TIKTOK_USERNAME }}}}")
nid += 1
add(result_node("TikTok Result", [3560, 1240], nid, "tiktok", TT_LINK))
nid += 1
add(failed_node("TikTok Failed", [3560, 1500], nid, "tiktok"))

# --- done -------------------------------------------------------------------
nid += 1
add(code_node("Summarize Results", [900, 300], nid, SUMMARY_CODE))
nid += 1
add(node("Send Results Card", "n8n-nodes-base.telegram", 1.2, [1140, 20], {
    "chatId": "={{ $('Start').first().json.chat_id }}",
    "text": "=📣 <b>Publishing results</b>\n\n{{ $json.summary_html }}",
    "additionalFields": {"appendAttribution": False, "parse_mode": "HTML", "disable_web_page_preview": True},
}, nid, onError="continueRegularOutput"))
nid += 1
add(set_node("Return", [1400, 20], nid, [
    ("results", "={{ $('Summarize Results').item.json.results }}", "array"),
    ("ok_count", "={{ $('Summarize Results').item.json.ok_count }}", "number"),
    ("failed_count", "={{ $('Summarize Results').item.json.failed_count }}", "number"),
    ("summary_text", "={{ $('Summarize Results').item.json.summary_text }}", "string"),
]))


def c(target, index=0):
    return {"node": target, "type": "main", "index": index}


connections = {
    "Start": {"main": [[c("Config")]]},
    "Config": {"main": [[c("Plan Posts")]]},
    "Plan Posts": {"main": [[c("Loop Over Items")]]},
    # output 0 = done, output 1 = loop
    "Loop Over Items": {"main": [[c("Summarize Results")], [c("Route by Platform")]]},
    "Route by Platform": {"main": [[c("Skipped")], [c("FB Media Type")], [c("IG Create Container")], [c("Resolve Refresh Token")]]},
    "Skipped": {"main": [[c("Loop Over Items")]]},
    # Facebook
    "FB Media Type": {"main": [[c("FB Post Video")], [c("FB Post Photo")], [c("FB Post Text")]]},
    "FB Post Video": {"main": [[c("FB Result")], [c("FB Failed")]]},
    "FB Post Photo": {"main": [[c("FB Result")], [c("FB Failed")]]},
    "FB Post Text": {"main": [[c("FB Result")], [c("FB Failed")]]},
    "FB Result": {"main": [[c("Loop Over Items")]]},
    "FB Failed": {"main": [[c("Loop Over Items")]]},
    # Instagram
    "IG Create Container": {"main": [[c("IG Wait 10s")], [c("IG Failed")]]},
    "IG Wait 10s": {"main": [[c("IG Check Container")]]},
    "IG Check Container": {"main": [[c("IG Ready?")], [c("IG Failed")]]},
    "IG Ready?": {"main": [[c("IG Publish")], [c("IG Failed or Timed Out?")]]},
    "IG Failed or Timed Out?": {"main": [[c("IG Failed")], [c("IG Wait 10s")]]},
    "IG Publish": {"main": [[c("IG Get Permalink")], [c("IG Failed")]]},
    "IG Get Permalink": {"main": [[c("IG Result")]]},
    "IG Result": {"main": [[c("Loop Over Items")]]},
    "IG Failed": {"main": [[c("Loop Over Items")]]},
    # TikTok
    "Resolve Refresh Token": {"main": [[c("Refresh TikTok Token")], [c("TikTok Failed")]]},
    "Refresh TikTok Token": {"main": [[c("Persist Tokens")], [c("TikTok Failed")]]},
    "Persist Tokens": {"main": [[c("Download Video")], [c("TikTok Failed")]]},
    "Download Video": {"main": [[c("Measure Video")], [c("TikTok Failed")]]},
    "Measure Video": {"main": [[c("TikTok Init Upload")], [c("TikTok Failed")]]},
    "TikTok Init Upload": {"main": [[c("Reattach Video")], [c("TikTok Failed")]]},
    "Reattach Video": {"main": [[c("TikTok Upload Bytes")], [c("TikTok Failed")]]},
    "TikTok Upload Bytes": {"main": [[c("TikTok Wait 15s")], [c("TikTok Failed")]]},
    "TikTok Wait 15s": {"main": [[c("TikTok Fetch Status")]]},
    "TikTok Fetch Status": {"main": [[c("TikTok Published?")], [c("TikTok Failed")]]},
    "TikTok Published?": {"main": [[c("TikTok Result")], [c("TikTok Failed or Timed Out?")]]},
    "TikTok Failed or Timed Out?": {"main": [[c("TikTok Failed")], [c("TikTok Wait 15s")]]},
    "TikTok Result": {"main": [[c("Loop Over Items")]]},
    "TikTok Failed": {"main": [[c("Loop Over Items")]]},
    # done
    "Summarize Results": {"main": [[c("Send Results Card")]]},
    "Send Results Card": {"main": [[c("Return")]]},
}

# sanity: every connection target must exist
names = {n["name"] for n in nodes}
for src, outs in connections.items():
    assert src in names, src
    for out in outs["main"]:
        for tgt in out:
            assert tgt["node"] in names, tgt["node"]

workflow = {
    "name": "Dainuie – Publish Post (tool)",
    "id": "dainuie-publish",
    "active": False,
    "settings": {"executionOrder": "v1"},
    "meta": {"templateCredsSetupCompleted": False},
    "tags": [],
    "pinData": {},
    "nodes": nodes,
    "connections": connections,
}

out = pathlib.Path(__file__).resolve().parents[1] / "workflows" / "04-dainuie-publish-post.json"
out.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {out} ({len(nodes)} nodes)")
