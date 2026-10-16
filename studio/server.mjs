#!/usr/bin/env node
/**
 * Studio: a local review board for the videos, wired into the running Claude Code session.
 *
 * It is a Claude Code channel (the pattern of Anthropic's fakechat demo): Claude Code spawns this
 * file over stdio, and anything the owner types or clicks on http://localhost:8790 arrives in the
 * session as a <channel source="studio"> message. Claude answers through the `reply` tool, which
 * can attach images and videos, and sets the board's status line with `status`.
 *
 * Start it with studio/start.sh (custom channels need --dangerously-load-development-channels
 * during the research preview). Local only: bound to 127.0.0.1, the Host header must be ours
 * (no DNS rebinding) and every POST carries a per-launch token that only our own page can read,
 * so another web page can't put words in front of Claude.
 */
import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { ListToolsRequestSchema, CallToolRequestSchema } from '@modelcontextprotocol/sdk/types.js'
import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const PORT = Number(process.env.STUDIO_PORT ?? 8790)
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const VIDEOS = path.join(ROOT, 'videos')
const PLANS = path.join(ROOT, 'pipeline', 'plans')
const POSTS = path.join(ROOT, 'pipeline', 'posts.json')
const STATE = path.join(VIDEOS, 'studio')          // gitignored with the rest of videos/
const CACHE = path.join(STATE, 'cache')            // clips and thumbnails unpacked from raw/<slug>.tar
const OUTBOX = path.join(STATE, 'outbox')          // reply attachments that live outside videos/
const CHAT = path.join(STATE, 'chat.jsonl')
const REVIEWS = path.join(STATE, 'reviews.json')
const TOKEN = crypto.randomBytes(16).toString('hex')
const HOSTS = new Set([`127.0.0.1:${PORT}`, `localhost:${PORT}`])
fs.mkdirSync(OUTBOX, { recursive: true })

const log = (...a) => process.stderr.write(`studio: ${a.join(' ')}\n`)  // stdout is the MCP pipe

// ---------- state the page shows ----------
const clients = new Set()   // open SSE responses
let status = ''

function broadcast(ev) {
  const data = `data: ${JSON.stringify(ev)}\n\n`
  for (const res of clients) res.write(data)
}

function remember(msg) {
  fs.appendFileSync(CHAT, JSON.stringify(msg) + '\n')
  broadcast({ type: 'msg', ...msg })
}

function history(n = 300) {
  try {
    return fs.readFileSync(CHAT, 'utf8').trim().split('\n').filter(Boolean).slice(-n).map(l => JSON.parse(l))
  } catch { return [] }
}

const readJSON = (p, d) => { try { return JSON.parse(fs.readFileSync(p, 'utf8')) } catch { return d } }

// ---------- the videos ----------
function planFor(stem) {
  // "2026-10-31-back-from-the-dead-max-cuts" is a re-edit of plan "...-max": take the longest plan
  // whose name starts the video's name
  const names = fs.readdirSync(PLANS).filter(f => f.endsWith('.json')).map(f => f.slice(0, -5))
  const hit = names.filter(n => stem === n || stem.startsWith(n + '-')).sort((a, b) => b.length - a.length)[0]
  return hit ? { name: hit, plan: readJSON(path.join(PLANS, hit + '.json'), null) } : { name: null, plan: null }
}

function listVideos() {
  const posts = readJSON(POSTS, {})
  return fs.readdirSync(VIDEOS).filter(f => /^\d{4}-\d\d-\d\d-.+\.mp4$/.test(f)).sort().reverse().map(f => {
    const stem = f.slice(0, -4)
    const { plan } = planFor(stem)
    const slug = plan?.slug ?? stem.slice(11)
    const st = fs.statSync(path.join(VIDEOS, f))
    return {
      id: stem, date: stem.slice(0, 10), slug, file: `videos/${f}`, mtime: st.mtimeMs,
      title: plan?.song?.title ?? slug, product: plan?.product ?? null, shots: plan?.shots?.length ?? 0,
      raw: fs.existsSync(path.join(VIDEOS, 'raw', `${slug}.tar`)), post: posts[stem]?.status ?? null,
    }
  })
}

function unpack(slug) {
  // the clips, timeline and lyrics of a render, from its raw tar, once
  const dir = path.join(CACHE, slug)
  const tar = path.join(VIDEOS, 'raw', `${slug}.tar`)
  if (!fs.existsSync(tar)) return null
  const stamp = path.join(dir, '.from')
  const mtime = String(fs.statSync(tar).mtimeMs)
  if (fs.existsSync(stamp) && fs.readFileSync(stamp, 'utf8') === mtime) return dir
  fs.rmSync(dir, { recursive: true, force: true })
  fs.mkdirSync(dir, { recursive: true })
  execFileSync('tar', ['xf', tar, '-C', dir, '--exclude', '*.flac', '--exclude', '*.wav', '--exclude', '*.pt'])
  for (const c of fs.readdirSync(path.join(dir, 'clips')).filter(f => f.endsWith('.mp4'))) {
    const jpg = path.join(dir, 'clips', c.replace('.mp4', '.jpg'))
    try {
      execFileSync('ffmpeg', ['-v', 'error', '-y', '-ss', '0.6', '-i', path.join(dir, 'clips', c), '-frames:v', '1',
        '-vf', 'scale=360:-2', '-q:v', '4', jpg])
    } catch (e) { log('thumb failed', c, e.message) }
  }
  fs.writeFileSync(stamp, mtime)
  return dir
}

function videoDetail(id) {
  const v = listVideos().find(x => x.id === id)
  if (!v) return null
  const { name, plan } = planFor(id)
  const dir = v.raw ? unpack(v.slug) : null
  const rel = p => path.relative(ROOT, p)
  const tl = dir ? readJSON(path.join(dir, 'timeline.json'), null) : null
  const lines = dir ? readJSON(path.join(dir, 'words_edit.json'), readJSON(path.join(dir, 'words.json'), [])) : []
  const reviews = readJSON(REVIEWS, {})[id] ?? {}
  const caption = (() => { try { return fs.readFileSync(path.join(VIDEOS, id + '.txt'), 'utf8') } catch { return '' } })()
  const shots = (plan?.shots ?? []).map((s, i) => {
    const clip = dir && path.join(dir, 'clips', `shot_${String(i).padStart(2, '0')}.mp4`)
    const has = clip && fs.existsSync(clip)
    const k = s.line
    return {
      i, prompt: s.prompt, line: k ?? null, sing: !!s.sing, product: !!s.product_image,
      lyric: Number.isInteger(k) && lines[k] ? lines[k].map(w => w.w ?? w.word ?? w.text ?? '').join(' ').trim() : null,
      start: tl?.shots?.[i]?.start ?? null, dur: tl?.shots?.[i]?.dur ?? null,
      clip: has ? rel(clip) : null, thumb: has ? rel(clip.replace('.mp4', '.jpg')) : null,
      review: reviews[i] ?? null,
    }
  })
  return { ...v, plan: name ? `pipeline/plans/${name}.json` : null, hook: plan?.hook_text ?? null,
    song: plan?.song ?? null, caption, shots, review: reviews.video ?? null }
}

function setReview(id, shot, mark, note) {
  const all = readJSON(REVIEWS, {})
  const r = (all[id] ??= {})
  const key = shot === null || shot === undefined ? 'video' : String(shot)
  if (!mark) delete r[key]
  else r[key] = { mark, note: note || '', ts: new Date().toISOString() }
  fs.writeFileSync(REVIEWS, JSON.stringify(all, null, 1))
}

// ---------- the channel ----------
const mcp = new Server(
  { name: 'studio', version: '0.1.0' },
  {
    capabilities: { tools: {}, experimental: { 'claude/channel': {} } },
    instructions: [
      'The owner is reviewing videos in the Studio page (http://localhost:' + PORT + ') and reads that page, not this terminal.',
      'Their messages arrive as <channel source="studio" chat_id="web" message_id="..." kind="..." video="..." shot="...">.',
      'kind is "chat" (typed), "redo" (they flagged a shot to re-render, with a note), "approve" (they want the video queued',
      'to post) or "keep" (they marked a shot good, for your information). video is the video id (videos/<id>.mp4, plan in',
      'pipeline/plans/), shot is the 0-based shot index. Their per-shot marks are saved in videos/studio/reviews.json.',
      'Answer every message with the reply tool: it is the only way they see anything. Keep replies short and plain, no em dashes.',
      'Pass absolute file paths in files to show images, videos or audio inline (a new render, a frame you extracted).',
      'Use the status tool for a one-line progress note on the board while something long runs (render 12/32, 6 min left),',
      'and clear it when done. After a render or re-edit finishes, reply with the new video attached.',
    ].join(' '),
  },
)

mcp.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'reply',
      description: 'Send a message to the owner in the Studio page. files: absolute paths of images, videos or audio to show inline.',
      inputSchema: {
        type: 'object',
        properties: {
          text: { type: 'string' },
          files: { type: 'array', items: { type: 'string' } },
          reply_to: { type: 'string', description: 'message_id being answered' },
        },
        required: ['text'],
      },
    },
    {
      name: 'status',
      description: 'Set the one-line status shown at the top of the Studio page (empty string clears it). The video list also refreshes.',
      inputSchema: { type: 'object', properties: { text: { type: 'string' } }, required: ['text'] },
    },
  ],
}))

function attach(f) {
  const abs = path.resolve(f)
  if (!fs.existsSync(abs)) throw new Error(`no such file: ${f}`)
  if (fs.statSync(abs).size > 300 * 1024 * 1024) throw new Error(`file too large: ${f}`)
  if (abs.startsWith(VIDEOS + path.sep)) return { url: '/' + path.relative(ROOT, abs), name: path.basename(abs) }
  const out = `${Date.now()}-${crypto.randomBytes(3).toString('hex')}${path.extname(abs).toLowerCase()}`
  fs.copyFileSync(abs, path.join(OUTBOX, out))
  return { url: '/' + path.relative(ROOT, path.join(OUTBOX, out)), name: path.basename(abs) }
}

mcp.setRequestHandler(CallToolRequestSchema, async req => {
  const a = req.params.arguments ?? {}
  try {
    if (req.params.name === 'reply') {
      const files = (a.files ?? []).map(attach)
      const id = `a${Date.now()}`
      remember({ id, from: 'claude', text: String(a.text ?? ''), files, replyTo: a.reply_to ?? null, ts: Date.now() })
      broadcast({ type: 'videos' })
      return { content: [{ type: 'text', text: `sent (${id})` }] }
    }
    if (req.params.name === 'status') {
      status = String(a.text ?? '')
      broadcast({ type: 'status', text: status })
      broadcast({ type: 'videos' })
      return { content: [{ type: 'text', text: 'ok' }] }
    }
    throw new Error(`unknown tool ${req.params.name}`)
  } catch (e) {
    return { content: [{ type: 'text', text: String(e.message ?? e) }], isError: true }
  }
})

function deliver(msg) {
  const where = [msg.video && `video ${msg.video}`, Number.isInteger(msg.shot) && `shot ${msg.shot}`].filter(Boolean).join(', ')
  const verb = { redo: 'redo', approve: 'approve', keep: 'keep' }[msg.kind]
  const content = (verb ? `[${verb}${where ? ' ' + where : ''}] ` : where ? `[about ${where}] ` : '') + (msg.text || '')
  const meta = { chat_id: 'web', message_id: msg.id, kind: msg.kind }
  if (msg.video) meta.video = msg.video
  if (Number.isInteger(msg.shot)) meta.shot = String(msg.shot)
  void mcp.notification({ method: 'notifications/claude/channel', params: { content, meta } })
}

await mcp.connect(new StdioServerTransport())

// ---------- HTTP ----------
const MIME = { '.mp4': 'video/mp4', '.mov': 'video/quicktime', '.webm': 'video/webm', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp', '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.flac': 'audio/flac',
  '.m4a': 'audio/mp4', '.json': 'application/json', '.txt': 'text/plain; charset=utf-8' }
const PAGE = fs.readFileSync(path.join(ROOT, 'studio', 'index.html'), 'utf8')

function sendFile(req, res, abs) {
  // Range support: browsers need it to seek in a video
  let st
  try { st = fs.statSync(abs) } catch { res.writeHead(404).end(); return }
  const type = MIME[path.extname(abs).toLowerCase()] ?? 'application/octet-stream'
  const m = /bytes=(\d*)-(\d*)/.exec(req.headers.range ?? '')
  if (m) {
    const start = m[1] ? Number(m[1]) : st.size - Number(m[2])
    const end = m[1] && m[2] ? Math.min(Number(m[2]), st.size - 1) : st.size - 1
    res.writeHead(206, { 'Content-Type': type, 'Content-Range': `bytes ${start}-${end}/${st.size}`,
      'Accept-Ranges': 'bytes', 'Content-Length': end - start + 1 })
    fs.createReadStream(abs, { start, end }).pipe(res)
  } else {
    res.writeHead(200, { 'Content-Type': type, 'Content-Length': st.size, 'Accept-Ranges': 'bytes' })
    fs.createReadStream(abs).pipe(res)
  }
}

const json = (res, body, code = 200) => res.writeHead(code, { 'Content-Type': 'application/json' }).end(JSON.stringify(body))

async function body(req) {
  let s = ''
  for await (const c of req) { s += c; if (s.length > 100_000) throw new Error('too big') }
  return JSON.parse(s || '{}')
}

const server = http.createServer(async (req, res) => {
  if (!HOSTS.has(req.headers.host ?? '')) return res.writeHead(403).end('bad host')
  const url = new URL(req.url, `http://${req.headers.host}`)
  const p = decodeURIComponent(url.pathname)
  try {
    if (req.method === 'GET') {
      if (p === '/') return res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' })
        .end(PAGE.replace('__TOKEN__', TOKEN))
      if (p === '/events') {
        res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', Connection: 'keep-alive' })
        res.write(`data: ${JSON.stringify({ type: 'status', text: status })}\n\n`)
        clients.add(res)
        const ping = setInterval(() => res.write(': ping\n\n'), 25_000)
        req.on('close', () => { clients.delete(res); clearInterval(ping) })
        return
      }
      if (p === '/api/videos') return json(res, listVideos())
      if (p === '/api/chat') return json(res, history())
      if (p.startsWith('/api/video/')) {
        const d = videoDetail(p.slice(11))
        return d ? json(res, d) : json(res, { error: 'not found' }, 404)
      }
      if (p.startsWith('/videos/')) {
        const abs = path.resolve(ROOT, '.' + p)
        if (!abs.startsWith(VIDEOS + path.sep)) return res.writeHead(403).end()
        return sendFile(req, res, abs)
      }
      return res.writeHead(404).end()
    }
    if (req.method === 'POST') {
      if (req.headers['x-studio-token'] !== TOKEN) return res.writeHead(403).end('bad token')
      const b = await body(req)
      if (p === '/api/send') {
        const kind = ['chat', 'redo', 'approve', 'keep'].includes(b.kind) ? b.kind : 'chat'
        const shot = Number.isInteger(b.shot) ? b.shot : null
        const video = typeof b.video === 'string' && /^[\w-]+$/.test(b.video) ? b.video : null
        const text = String(b.text ?? '').slice(0, 4000).trim()
        if (!text && kind === 'chat') return json(res, { error: 'empty' }, 400)
        if (kind !== 'chat' && video) setReview(video, shot, kind, text)
        const msg = { id: `u${Date.now()}`, from: 'owner', text, kind, video, shot, ts: Date.now() }
        remember(msg)
        if (kind !== 'keep') deliver(msg)   // a thumbs-up is saved for later, not worth a turn
        return json(res, { ok: true, id: msg.id })
      }
      if (p === '/api/unmark') {
        setReview(b.video, Number.isInteger(b.shot) ? b.shot : null, null)
        return json(res, { ok: true })
      }
    }
    res.writeHead(404).end()
  } catch (e) {
    log('error', p, e.message)
    if (!res.headersSent) json(res, { error: e.message }, 500)
  }
})
server.on('error', e => log(e.code === 'EADDRINUSE' ? `port ${PORT} is taken (another session has the Studio open?)` : e.message))
server.listen(PORT, '127.0.0.1', () => log(`http://localhost:${PORT}`))
