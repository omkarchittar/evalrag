# Recorded product demonstration

The GIF in the README is a recording of the production Next.js app running with FastAPI, a separate worker and disposable PostgreSQL/pgvector. It shows document ingestion, a grounded answer, exact source evidence, reference-case editing, a semantic evaluation and case inspection.

All documents and accounts are fictional. The model endpoint is a **controlled local fixture**, visibly named `controlled-browser-fixture`; scores and timings in the recording demonstrate integration behavior, not live-model quality. No product response is substituted in the frontend and no real credentials are used. The recording is resized and palette-encoded as a GIF; its application content is not edited.

To regenerate, install the frontend/backend development dependencies and Chromium, then from `frontend`:

```sh
TEST_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@localhost:5432/evalrag_test' npm run record:demo
node scripts/render-demo.mjs test-results/demo-record-the-evidence-to-evaluation-journey-demo/demo.webm
```

The PostgreSQL role needs CREATEDB, as in the browser tests. The script waits for actual UI states; brief pauses only provide reading time. FFmpeg must be installed with GIF encoding support; set `FFMPEG_BIN` to a working executable when it is not on PATH. The committed GIF was encoded with FFmpeg 7.1, 8 fps, 960-pixel width and a 128-color palette.

Recording uses [Playwright video capture](https://playwright.dev/docs/videos) and the same isolated provider fixture as the browser verification suite. No live-model API key is required. Temporary browser/database/server state is removed after recording.
