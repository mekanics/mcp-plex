# Plex MCP — User Flow Analysis

**Author:** UX/Workflow Analyst (subagent)
**Date:** 2026-02-18
**Purpose:** Document realistic user flows for a Plex Media Server MCP integration, identify tool sequences, edge cases, and gaps in the current toolset.

---

## Available Tools (Reference)

| Tool | Purpose |
|------|---------|
| `search_media` | Full-text search across libraries, with type filter |
| `browse_library` | List/filter/sort/paginate library contents |
| `get_media_details` | Rich metadata: cast, ratings, summary, file info |
| `now_playing` | Active streaming sessions |
| `on_deck` | Continue-watching list (in-progress media) |
| `recently_added` | New additions, filterable by date |
| `play_media` | Start playback on a client device |
| `playback_control` | Pause / resume / stop / skip |

---

## Flow Index

1. [What Should I Watch Tonight?](#flow-1-what-should-i-watch-tonight)
2. [Resume Where I Left Off](#flow-2-resume-where-i-left-off)
3. [Find and Play a Specific Title](#flow-3-find-and-play-a-specific-title)
4. [Is Anyone Streaming Right Now?](#flow-4-is-anyone-streaming-right-now)
5. [Power Browse — Unwatched 4K Movies](#flow-5-power-browse--unwatched-4k-movies)
6. [What Was Added This Week?](#flow-6-what-was-added-this-week)
7. [Remote Playback Control](#flow-7-remote-playback-control)
8. [Research Before Watching](#flow-8-research-before-watching)
9. [Something for the Kids](#flow-9-something-for-the-kids)
10. [Fuzzy / Half-Remembered Search](#flow-10-fuzzy--half-remembered-search)
11. [Actor-Based Discovery](#flow-11-actor-based-discovery)
12. [Binge a Full Season](#flow-12-binge-a-full-season)
13. [Multi-User Monitoring Dashboard](#flow-13-multi-user-monitoring-dashboard)
14. [Compare Two Titles Before Deciding](#flow-14-compare-two-titles-before-deciding)

---

## Flow 1: What Should I Watch Tonight?

### User Intent
A casual user wants a recommendation from their own library. They haven't decided on anything and want suggestions.

> *"I don't know what to watch tonight — give me some ideas."*

### Tool Sequence
```
on_deck()
  → [list of in-progress items]
recently_added(days=14)
  → [recent additions]
browse_library(sort=rating, limit=10)
  → [top-rated items]
get_media_details(id) [×2–3 for top candidates]
  → [summaries, ratings, runtime]
```

### Key Data Flow
- `on_deck` reveals partially-watched content (implicit preference signal)
- `recently_added` surfaces freshness bias ("something new")
- `browse_library` sorted by rating gives quality signal
- `get_media_details` provides the human-readable pitch: summary, rating, runtime, genre

### Edge Cases
- **Empty on_deck:** User hasn't watched anything recently — skip or note this
- **Library too large:** Browsing returns hundreds of items; agent must curate, not dump
- **No rating metadata:** Many items may lack audience/critic ratings; fallback to recently added
- **User mood mismatch:** "Give me something funny" needs genre awareness — `browse_library` must support genre filter
- **Duplicate suggestions:** on_deck and recently_added may overlap; dedup before presenting

### Example Dialogue
```
User:  I don't know what to watch — surprise me.

Agent: I looked at your library and have three picks:

       🎬 **Oppenheimer** (2023) — You're 40 min in already. Runtime left: ~2h50m.
          "A gripping historical epic. 8.9/10 on IMDb."

       🆕 **Severance S2** — Just added 3 days ago. You haven't started it.
          "Sci-fi thriller, 9 episodes. Perfect for a binge."

       ⭐ **The Godfather** — Highest-rated unwatched film in your library.
          "If you're in the mood for a classic."

       Which sounds good, or should I filter by mood/genre?
```

### Missing Tool Need
- `browse_library` needs **genre filter** and **watched status filter** to be useful here
- A `get_library_stats` or `get_user_preferences` tool would allow smarter personalization

---

## Flow 2: Resume Where I Left Off

### User Intent
The user wants to pick up exactly where they stopped — could be a movie or a TV episode.

> *"Resume what I was watching last night."*

### Tool Sequence
```
on_deck()
  → [list of in-progress items, sorted by last-watched timestamp]
get_media_details(id) [for top result]
  → [title, episode info, resume position]
play_media(media_id, client_id, resume=true)
  → [playback started at resume point]
```

### Key Data Flow
- `on_deck` returns items with `viewOffset` (milliseconds into the content) and `lastViewedAt` timestamp
- Agent identifies the most-recently-watched item
- `play_media` passes `viewOffset` or a `resume` flag so Plex resumes at the right point
- `client_id` must be resolved — this is a **gap** (see Edge Cases)

### Edge Cases
- **Multiple in-progress items:** User was watching both a movie and a show. Agent needs to ask or pick the most recent.
- **Unknown client:** `play_media` requires a target device. Agent doesn't know which TV/device to use without a `get_clients` tool.
- **Near the end:** Item is 95%+ complete — should agent suggest starting the next episode instead?
- **Shared household:** "I" vs. another user's in-progress content (no user context in current tools)
- **Resume vs. restart:** Some users want to restart, not resume — agent should ask if ambiguous

### Example Dialogue
```
User:  Resume what I was watching.

Agent: You were in the middle of **Severance S1E4 — "The Grim Barbarity of Optics
       and Titles"** — about 28 minutes in (44 min remaining).

       Which device should I play it on?
       • Living Room TV (Plex for Android TV)
       • MacBook (Plex Web)

User:  Living room TV.

Agent: ▶ Resuming Severance on Living Room TV from 28:14.
```

### Missing Tool Need
- **`get_clients()`** — critical. Without listing available playback clients, `play_media` cannot be called without hardcoding a client ID.

---

## Flow 3: Find and Play a Specific Title

### User Intent
The user knows exactly what they want to watch and wants a one-shot command to find and play it.

> *"Play Interstellar on my TV."*

### Tool Sequence
```
search_media(query="Interstellar", type="movie")
  → [search results with media IDs]
get_media_details(id) [if multiple results or to confirm]
  → [year, summary — to disambiguate]
play_media(media_id, client_id)
  → [playback started]
```

### Key Data Flow
- `search_media` returns a ranked list of matches with IDs
- If exactly one confident match → proceed directly to `play_media`
- If multiple matches (e.g., "The Fly" — 1958 vs. 1986) → surface disambiguation to user
- `client_id` still requires resolution (see missing tools)

### Edge Cases
- **Typo/alternate title:** "Intersteller" or "that space movie with Matthew McConaughey" — search must handle fuzzy input
- **Not in library:** Title doesn't exist. Agent should say so clearly rather than playing wrong content.
- **Multiple editions:** Library has Theatrical + Extended Cut. Which does the user want?
- **Client ambiguity:** "My TV" is ambiguous in multi-TV households
- **Already playing:** Content is already playing on that client — prompt to stop first?

### Example Dialogue
```
User:  Play Interstellar on the living room TV.

Agent: Found it — **Interstellar** (2014, Christopher Nolan, 2h49m).
       Starting on Living Room TV now.

       ▶ Playing.

---

User:  Play The Fly.

Agent: I found two versions in your library:
       1. The Fly (1958) — Vincent Price, horror classic
       2. The Fly (1986) — Jeff Goldblum, body horror remake

       Which one?
```

---

## Flow 4: Is Anyone Streaming Right Now?

### User Intent
A server owner wants to see who's currently using the Plex server — monitoring or curiosity.

> *"Is anyone watching Plex right now?"*

### Tool Sequence
```
now_playing()
  → [active sessions: user, title, client, progress, bandwidth, transcode status]
```

### Key Data Flow
- `now_playing` returns session objects with: username, media title, playback position, client device, stream type (direct play vs. transcode), bandwidth usage
- Agent formats this into a human-readable summary

### Edge Cases
- **No active sessions:** Return a clear "nothing playing" rather than an empty list dump
- **Multiple sessions:** Server has 5 concurrent streams — bandwidth concerns may be relevant
- **Transcoding sessions:** Some streams are CPU-intensive transcodes; relevant for server health context
- **Paused sessions:** Are paused streams shown in now_playing? Depends on Plex API behavior — agent should note "paused" state
- **Privacy concern:** In shared servers, surfacing who watches what may be sensitive

### Example Dialogue
```
User:  Is anyone watching Plex right now?

Agent: Yes — 2 active streams:

       👤 **Alex** — Watching *The Bear S3E2* on iPad
          Progress: 14:32 / 42:18 | Direct Play | 8 Mbps

       👤 **Jordan** — Watching *Dune: Part Two* on Apple TV
          Progress: 1:02:00 / 2:46:00 | Transcoding (H.265→H.264) | 12 Mbps

       Total bandwidth: ~20 Mbps. Transcoding is active — CPU load may be elevated.
```

### Missing Tool Need
- **`get_server_info()`** — to correlate with CPU/RAM/bandwidth metrics for a true health dashboard

---

## Flow 5: Power Browse — Unwatched 4K Movies

### User Intent
A power user wants to filter their library with specific technical and watch-status criteria.

> *"Show me all the unwatched 4K movies in my library, sorted by rating."*

### Tool Sequence
```
browse_library(
  type="movie",
  filter={resolution: "4k", watched: false},
  sort="rating",
  limit=25
)
  → [paginated list of matching titles]
```

### Key Data Flow
- `browse_library` must support compound filters: media type + resolution + watched status + sort
- Returns list of titles with basic metadata (year, rating, runtime)
- User may follow up with `get_media_details` on specific items

### Edge Cases
- **Filter not supported:** If `browse_library` doesn't support resolution or watched-status filters, this flow fails entirely — **this is likely a tool gap**
- **4K defined inconsistently:** "4K" could mean UHD Blu-ray (2160p), HDR, Dolby Vision, or just a high-res file. Metadata labeling varies.
- **Large result sets:** User may have 200+ 4K movies. Pagination UX matters.
- **No 4K content:** User doesn't have any — agent should say so, not return empty silently
- **Rating metadata gaps:** Many items may lack ratings; sort by rating produces incomplete ordering

### Example Dialogue
```
User:  Show me all my unwatched 4K movies, best first.

Agent: Found 34 unwatched 4K movies in your library. Top 10 by rating:

       1. ⭐ 9.0 — The Godfather (1972, 2h55m) [4K HDR]
       2. ⭐ 8.9 — Oppenheimer (2023, 3h1m) [4K Dolby Vision]
       3. ⭐ 8.8 — Parasite (2019, 2h12m) [4K HDR]
       ...
       [25 more — say "next page" or filter by genre]

User:  Filter to just sci-fi.

Agent: 8 unwatched 4K sci-fi movies:
       1. Dune: Part Two (2024) — ⭐ 8.5
       ...
```

### Missing Tool Need
- `browse_library` needs explicit support for: **resolution filter**, **watched status filter**, **genre filter** — these are fundamental power-user features likely absent from a naive implementation

---

## Flow 6: What Was Added This Week?

### User Intent
A user checks in periodically to see what's new on their server, like browsing a streaming service's "New" section.

> *"What's new on Plex this week?"*

### Tool Sequence
```
recently_added(days=7)
  → [list of media added in last 7 days, grouped by type]
get_media_details(id) [×2–3 for highlights]
  → [summaries for the most interesting additions]
```

### Key Data Flow
- `recently_added` returns items with `addedAt` timestamps, media type, and basic metadata
- Agent groups by type (Movies / TV Shows / Music) for readability
- For TV: ideally surfaces "Season 2 of Show X added" rather than "14 individual episodes added"
- Highlights 2–3 items with brief pitches from `get_media_details`

### Edge Cases
- **Episode-level noise:** TV additions show individual episodes, not seasons — agent must aggregate
- **Empty week:** Nothing was added. Return a clear message.
- **Large batch:** Someone did a big import — 200 movies added at once. Agent must summarize, not list.
- **Date timezone ambiguity:** "This week" means different things. Clarify or default to 7 days.
- **Music libraries:** User may not care about music additions; agent should read context

### Example Dialogue
```
User:  Anything new on Plex this week?

Agent: 12 items added in the last 7 days:

       🎬 **Movies (4 new):**
       • Anora (2024) — Palme d'Or winner. "A whirlwind romance with consequences."
       • A Complete Unknown (2024) — Bob Dylan biopic with Timothée Chalamet
       • [2 more]

       📺 **TV Shows (2 shows, 8 episodes):**
       • Severance S2 — All 10 episodes added (new season!)
       • The White Lotus S3E1-2 — First two episodes of new season

       Anything catch your eye?
```

### Missing Tool Need
- **Episode aggregation logic** should ideally be server-side, or `recently_added` needs a "group by series" option

---

## Flow 7: Remote Playback Control

### User Intent
User wants to control something currently playing — pause it, skip the intro, or stop it.

> *"Pause whatever's playing in the living room."*
> *"Skip ahead 30 seconds."*
> *"Stop the movie, I'm going to bed."*

### Tool Sequence
```
now_playing()
  → [active sessions with session IDs and client IDs]
playback_control(session_id, action="pause")
  → [confirmation]
```

### Key Data Flow
- `now_playing` identifies the session on the target client
- `session_id` or `client_id` passed to `playback_control`
- Action: pause / resume / stop / skip_forward / skip_back / next_episode
- Confirmation returned (success/failure)

### Edge Cases
- **Multiple active sessions:** "The living room" — agent must match by client name
- **No active session:** Nothing is playing to control
- **Ambiguous "skip":** Does "skip" mean +30 seconds, skip intro, or next episode?
- **Session ended between calls:** Race condition — session ended in the gap between `now_playing` and `playback_control`
- **Permission:** On a shared server, should any user be able to control another user's stream?

### Example Dialogue
```
User:  Pause the movie.

Agent: Paused **Dune: Part Two** on Living Room TV at 1:02:14.

---

User:  Skip the intro.

Agent: ⏭ Skipped intro — jumped to 0:04:20 on Living Room TV.

---

User:  Stop everything, I'm going to bed.

Agent: Stopped 2 active streams:
       • Dune: Part Two (Living Room TV) — stopped at 1:02:14
       • The Bear (iPad) — stopped at 14:32

       Good night! 🌙
```

### Missing Tool Need
- `playback_control` should support **seek to position** (not just skip forward/back) and **skip intro** (Plex has this metadata)
- A **`get_clients()`** tool is needed to translate "living room" to a client ID

---

## Flow 8: Research Before Watching

### User Intent
User has heard about a movie and wants details before committing to watching it — cast, plot, runtime, ratings.

> *"Tell me about Parasite before I decide if I want to watch it."*

### Tool Sequence
```
search_media(query="Parasite", type="movie")
  → [match with media_id]
get_media_details(media_id)
  → [full metadata: summary, cast, director, ratings, runtime, genre, file info]
```

### Key Data Flow
- `get_media_details` returns the rich payload: plot summary, cast list, director, critic + audience ratings, runtime, content rating, genre tags, available audio/subtitle tracks, file size/codec
- Agent synthesizes this into a friendly pitch, not a data dump

### Edge Cases
- **Spoilers in summary:** Plot summaries can be spoiler-heavy. Agent should offer the pitch without spoiling the ending.
- **Not in library:** Movie exists on Plex but user is thinking of something they don't own yet — agent should clarify it IS in their library
- **Ambiguous query:** "Parasite" matches a 1982 horror film too (also possibly in library)
- **Rating disagreement:** Rotten Tomatoes 99% but audience score 90% — both are relevant context
- **Foreign language:** Film is in Korean — agent should note subtitles available

### Example Dialogue
```
User:  Tell me about Parasite.

Agent: **Parasite** (2019) — Directed by Bong Joon-ho
       🏆 Won 4 Academy Awards including Best Picture

       📝 *A poor Korean family schemes to become employed by a wealthy family,
          but their plan takes a dark, unexpected turn.*

       ⏱ Runtime: 2h12m | 🔞 Rated R | 🇰🇷 Korean with English subtitles
       ⭐ Critics: 99% | Audience: 90%
       🎭 Cast: Song Kang-ho, Lee Sun-kyun, Cho Yeo-jeong

       Available in: 1080p (H.265, 8.2 GB)

       Want me to play it, or looking for something else?
```

---

## Flow 9: Something for the Kids

### User Intent
Parent wants to find age-appropriate content quickly, often with a genre/mood filter.

> *"Find something for the kids to watch — something animated, not too long."*

### Tool Sequence
```
browse_library(
  type="movie",
  filter={content_rating: ["G", "PG"], genre: "animation"},
  sort="rating",
  limit=10
)
  → [filtered list]
get_media_details(id) [×2–3 top results]
  → [age-appropriate summary, runtime]
play_media(media_id, client_id)
  → [playback on kids' device]
```

### Key Data Flow
- Content rating filter is critical (G/PG/TV-Y/TV-G/TV-PG)
- Runtime filter helps ("not too long" = under 90 min)
- Genre filter: "animation" or "family"
- Results pitched with kid-friendly framing

### Edge Cases
- **Content rating metadata missing:** Many files lack proper content rating tags — G-rated content may not be labeled
- **"Animation" isn't always kids:** Spider-Man: Into the Spider-Verse (PG) vs. Arcane (TV-MA)
- **Age specificity:** "Kids" could mean toddlers (Bluey) or tweens (Harry Potter). Agent should ask age.
- **Already watched everything:** Kids have seen all the animated films. Agent should check watched status.
- **Which device:** "Kids TV" needs client resolution

### Example Dialogue
```
User:  Find something animated for the kids, under 90 minutes.

Agent: How old are the kids? (Helps me avoid Bluey for 12-year-olds and Arcane for 5-year-olds)

User:  7 and 9.

Agent: Great picks for that age group in your library:

       🎬 **Moana** (2016, PG, 1h47m) — "She'll love the music; he'll love the ocean adventure."
       🎬 **Spider-Man: Into the Spider-Verse** (2018, PG, 1h56m) — "Stunning animation, great story for both ages."
       🎬 **The Incredibles** (2004, PG, 1h55m) — "Superhero family comedy, holds up perfectly."

       Note: All are just over 90 min — closest I found. Want me to look for strictly under 90?

User:  Spider-Verse. Put it on the kids' TV.

Agent: ▶ Playing Spider-Man: Into the Spider-Verse on Kids Room TV.
```

---

## Flow 10: Fuzzy / Half-Remembered Search

### User Intent
User can't remember the exact title but describes the film from memory — plot, actor, vague details.

> *"There's this movie about a guy who goes back in time and... I think it has Tom Hanks? It's in my library somewhere."*

### Tool Sequence
```
search_media(query="Tom Hanks time travel")
  → [results — likely poor due to vagueness]
browse_library(filter={cast: "Tom Hanks"})
  → [all Tom Hanks films in library]
get_media_details(id) [×multiple]
  → [summaries — agent pattern-matches against description]
```

### Key Data Flow
- First search attempt with combined terms
- Fallback: filter by actor name if cast-filter is supported
- Agent reads plot summaries from `get_media_details` and matches against the user's description
- This is heavily LLM-side reasoning — the agent is the intelligence layer

### Edge Cases
- **Actor not in library:** Tom Hanks films may not be in their collection at all
- **Description ambiguous:** "Time travel Tom Hanks" could be nothing — wrong memory
- **Cast filter not supported:** `browse_library` may not support cast-based filtering — **likely gap**
- **Many results:** Tom Hanks has dozens of films; browsing all of them is expensive
- **Wrong actor memory:** User misremembers the actor — agent should gently probe

### Example Dialogue
```
User:  There's a movie where... I think Tom Hanks ends up in an airport? Or stuck somewhere?
       Can't remember the title.

Agent: That sounds like it could be **The Terminal** (2004) — Tom Hanks plays a man who gets
       stranded in a New York airport and has to live there. Steven Spielberg directed it.

       Is that the one? It's in your library.

User:  Yes! That's it. Play it.

Agent: ▶ Playing The Terminal on Living Room TV.
```

### Missing Tool Need
- `browse_library` or `search_media` needs a **cast/actor filter** to efficiently find all content featuring a specific person
- This flow heavily depends on LLM knowledge to bridge fuzzy descriptions → titles; the MCP tools just need to confirm presence

---

## Flow 11: Actor-Based Discovery

### User Intent
User enjoyed an actor's performance and wants to explore more of their work from the existing library.

> *"I just finished watching Succession. What else do Brian Cox or Jeremy Strong have in my library?"*

### Tool Sequence
```
search_media(query="Brian Cox")
  → [results featuring Brian Cox]
search_media(query="Jeremy Strong")
  → [results featuring Jeremy Strong]
get_media_details(id) [for each result]
  → [confirm cast, get summary]
```

OR (if cast filter exists):
```
browse_library(filter={cast: "Brian Cox"})
browse_library(filter={cast: "Jeremy Strong"})
```

### Key Data Flow
- Two parallel searches or browses by actor name
- Results merged, deduplicated, sorted by relevance
- `get_media_details` confirms cast membership (search may surface false positives)
- Agent excludes Succession itself from results

### Edge Cases
- **Name collisions:** "Brian Cox" is also a physicist/TV presenter — metadata may be mixed
- **Sparse library:** Neither actor has other content in the library — agent should say so and perhaps suggest what *could* be added
- **Supporting vs. lead roles:** Actor appears in 3-second cameo; agent should note role size if available
- **Search returns TV episodes:** Search may return individual episodes rather than shows

### Example Dialogue
```
User:  What else do Jeremy Strong and Brian Cox have in my library?

Agent: Here's what I found:

       **Jeremy Strong:**
       • The Big Short (2015) — Supporting role alongside Christian Bale
       • Molly's Game (2017) — Supporting role
       • (Nothing else in your library)

       **Brian Cox:**
       • Braveheart (1995) — Supporting role
       • Troy (2004) — Supporting role as Agamemnon
       • (Nothing else)

       Neither has much beyond Succession in your collection. Want me to note some titles
       worth adding?
```

### Missing Tool Need
- **Cast-based filter in `browse_library`** — without this, the agent must search and then verify cast via `get_media_details` for each result, which is very expensive

---

## Flow 12: Binge a Full Season

### User Intent
User wants to start a TV show from the beginning, or continue a season, and watch multiple episodes in sequence.

> *"Start The Bear from Season 1 Episode 1 and play them all."*

### Tool Sequence
```
search_media(query="The Bear", type="show")
  → [show result with show_id]
get_media_details(show_id)
  → [season/episode list with episode IDs and order]
play_media(episode_id_S01E01, client_id)
  → [playback started]
[Plex auto-plays next episode natively, or agent queues them]
```

### Key Data Flow
- `get_media_details` for a show must return structured season/episode data (not just flat metadata)
- Episodes need ordered IDs so the agent can instruct Plex to queue them
- `play_media` may support a `playlist` or `autoplay` flag — unclear if this exists in the current tool
- Alternatively, Plex natively handles "play next episode" in the player

### Edge Cases
- **Partially watched season:** User has seen S1E1–4 already. Play from E5? Or from E1? Agent should check and ask.
- **Missing episodes:** Library has S1E1, E2, E4 — E3 is missing. Agent should warn.
- **Multi-season auto-continue:** After S1 finale, should it automatically continue to S2?
- **Special episodes:** Some shows have Episode 0 (pilot specials) or fractional episodes. Order matters.
- **Runtime warning:** "All episodes" of a 10-season show is 200+ hours — agent should sanity-check

### Example Dialogue
```
User:  Start The Bear from the beginning, play all of Season 1.

Agent: The Bear S1 has 8 episodes (~2h20m total). You've already seen E1–E3.

       Start from E4 (where you left off), or restart from E1?

User:  From E1, I want to rewatch.

Agent: ▶ Playing The Bear — S1E1 "System" on Living Room TV.
       Auto-play is on — episodes will continue automatically.
       (Season 1 runtime: ~2h20m total)
```

### Missing Tool Need
- **`play_media` needs playlist/queue support** — ability to queue multiple episodes in order
- `get_media_details` must return **structured episode data** (season number, episode number, episode IDs, runtime, watched status per episode)

---

## Flow 13: Multi-User Monitoring Dashboard

### User Intent
A server admin wants a holistic view of current activity — who's watching what, server load, and recent additions.

> *"Give me a status report on the Plex server."*

### Tool Sequence
```
now_playing()
  → [active sessions: users, titles, clients, transcode status, bandwidth]
on_deck()
  → [in-progress items — shows engagement]
recently_added(days=7)
  → [new content this week]
```

### Key Data Flow
- All three calls combined into a summary report
- `now_playing` → current load
- `on_deck` → engagement (who's actively using the server in general)
- `recently_added` → library health (content is being added)
- Agent synthesizes into a terse admin dashboard

### Edge Cases
- **No active sessions:** Server is idle — still useful to report
- **High transcode count:** Many transcodes = CPU pressure; relevant alert
- **Server info absent:** Without `get_server_info`, can't report CPU/RAM/disk usage — **significant gap**
- **User count vs. stream count:** A user might have 2 streams on 2 devices
- **Privacy:** Displaying all users' viewing habits requires admin role

### Example Dialogue
```
User:  Plex status report.

Agent: 📊 **Plex Server Status** — Wed Feb 18, 17:00 UTC

       **🎬 Now Playing (2 streams):**
       • Alex → The Bear S3E2 | iPad | Direct Play | 8 Mbps
       • Jordan → Dune: Part Two | Apple TV | Transcoding | 12 Mbps
       Total bandwidth: ~20 Mbps

       **📂 Recent Additions (last 7 days):**
       • 4 movies, 2 TV shows (8 episodes)

       **▶ On Deck (active watchers):**
       • 3 items in progress across library

       ⚠️ Note: I can't report CPU/RAM/disk without a server info tool.
          Consider adding `get_server_info` to the MCP.
```

### Missing Tool Need
- **`get_server_info()`** — CPU, RAM, disk space, Plex version, transcoder status
- **`list_users()`** — enumerate managed/shared users on the server

---

## Flow 14: Compare Two Titles Before Deciding

### User Intent
User is torn between two options and wants a side-by-side comparison to make a decision.

> *"Should I watch Oppenheimer or Killers of the Flower Moon tonight? Which is better?"*

### Tool Sequence
```
search_media(query="Oppenheimer", type="movie")
  → [media_id_A]
search_media(query="Killers of the Flower Moon", type="movie")
  → [media_id_B]
get_media_details(media_id_A)
  → [ratings, runtime, summary, genre]
get_media_details(media_id_B)
  → [ratings, runtime, summary, genre]
```

### Key Data Flow
- Two parallel searches → two media IDs
- Two `get_media_details` calls (can be parallelized)
- Agent synthesizes comparison: ratings, runtime, tone, genre, watched status

### Edge Cases
- **One not in library:** "Sorry, Killers of the Flower Moon isn't in your library — but Oppenheimer is."
- **Both watched:** Both are already fully watched — agent should note and pivot to "want to rewatch?"
- **Wildly different genres:** Comparison may be apples vs. oranges; agent should acknowledge
- **Runtime fatigue:** Both are 3+ hours — agent might note "both are long; maybe pick based on your energy level tonight"
- **User has a preference already:** "Which is better?" is subjective; agent should give honest take based on ratings, not just list facts

### Example Dialogue
```
User:  Oppenheimer or Killers of the Flower Moon — which should I watch tonight?

Agent: Both are in your library and unwatched. Here's the breakdown:

       | | Oppenheimer | Killers of the Flower Moon |
       |---|---|---|
       | Year | 2023 | 2023 |
       | Runtime | 3h1m | 3h26m |
       | Director | Christopher Nolan | Martin Scorsese |
       | IMDb | 8.9 ⭐ | 7.7 ⭐ |
       | Tone | Tense, cerebral thriller | Slow-burn crime drama |

       **My take:** If you want something propulsive and tightly edited, Oppenheimer.
       If you want a meditative, emotional epic with stunning performances, go Flower Moon.
       Both are long — pick based on your energy tonight.

User:  Oppenheimer it is. Play it.

Agent: ▶ Playing Oppenheimer on Living Room TV.
```

---

## Missing Tools Summary

The current 8-tool set covers the basics but has significant gaps for realistic flows:

| Missing Tool | Why It's Needed | Flows Affected |
|---|---|---|
| **`get_clients()`** | List available playback devices by name/ID — without this, `play_media` is unusable without hardcoded IDs | 2, 3, 7, 9, 12 |
| **`browse_library` cast filter** | Filter library by actor/director name | 10, 11 |
| **`browse_library` resolution filter** | Filter by 4K/1080p/etc. | 5 |
| **`browse_library` watched-status filter** | Unwatched/watched/in-progress filter | 5, 9 |
| **`browse_library` content-rating filter** | G/PG/R filtering for parental control flows | 9 |
| **`get_server_info()`** | CPU, RAM, disk, transcoder health for admin monitoring | 4, 13 |
| **`list_users()`** | Enumerate managed/home users on server | 13 |
| **`get_libraries()`** | List library names and IDs — needed to target `browse_library` correctly | 1, 5, 6 |
| **`play_media` playlist/queue** | Queue multiple episodes for binge watching | 12 |
| **`get_watch_history()`** | What has been watched, when, by whom — for personalization | 1, 11 |
| **`manage_watchlist()`** | Add/remove items from a user's watchlist | 8, 10 |
| **`get_episode_list(show_id, season)`** | Structured season/episode data separate from `get_media_details` | 12 |

---

## Cross-Flow Observations

### The Client Resolution Problem
Nearly every flow that ends in playback (`play_media`) requires a `client_id`. Without `get_clients()`, the agent either:
- Requires the user to know and state their client ID (terrible UX)
- Hardcodes device names out-of-band (fragile)
- Cannot play anything (broken flow)

**This is the single most critical missing tool.**

### The Intelligence Layer
Many flows (fuzzy search, recommendations, comparisons) rely heavily on the LLM's own knowledge to bridge gaps — identifying movies from descriptions, synthesizing recommendations from metadata. The MCP tools are the data access layer; the LLM is the reasoning layer. This is correct architecture, but it means tool output quality (rich metadata in `get_media_details`) directly impacts flow quality.

### Parallelism Opportunities
Multiple flows benefit from **parallel tool calls**:
- Flow 14: Both `get_media_details` calls can be concurrent
- Flow 11: Both actor searches can be concurrent
- Flow 13: All three status calls can be concurrent

The MCP implementation should not impose artificial serialization.

### Pagination UX
`browse_library` returns paginated results. Agents need to handle:
- "Show me more" continuations
- Knowing total result count upfront
- Not auto-fetching all pages on large libraries (expensive)

---

*Generated by UX/workflow analysis subagent | 2026-02-18*
