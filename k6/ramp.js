// Ramp test (Phase 3, M8): find where p95 degrades and errors appear on the
// non-AI endpoints. 1 → 20 VUs over ~6 minutes, read-heavy with an optional
// write cycle (add + delete a library book) so the DB pool sees some writes.
//
//   TR_BASE_URL=https://<render-app>.onrender.com TR_JWT=<test-account-jwt> \
//     k6 run k6/ramp.js
//   # enable the write cycle (creates + deletes rows for the TEST account):
//   TR_WRITES=1 TR_BASE_URL=... TR_JWT=... k6 run k6/ramp.js
//
// Run the SAME script before and after any performance change — that identical
// re-run is the whole point (PERF-BASELINE.md records both sides).
// NEVER load-test /summarise, /recommend, /library/query, or /curate.
import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.TR_BASE_URL || "http://localhost:8000";
const JWT = __ENV.TR_JWT || "";
const WRITES = __ENV.TR_WRITES === "1";

export const options = {
  scenarios: {
    ramp: {
      executor: "ramping-vus",
      startVUs: 1,
      stages: [
        { duration: "1m", target: 5 },
        { duration: "2m", target: 10 },
        { duration: "2m", target: 20 },
        { duration: "1m", target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.02"],
    "http_req_duration{endpoint:library}": ["p(95)<2000"],
    "http_req_duration{endpoint:shelves}": ["p(95)<2000"],
    "http_req_duration{endpoint:health}": ["p(95)<1000"],
  },
};

const auth = { Authorization: `Bearer ${JWT}` };

export default function () {
  check(
    http.get(`${BASE}/health`, { tags: { endpoint: "health" } }),
    { "health 200": (r) => r.status === 200 }
  );
  check(
    http.get(`${BASE}/library`, { headers: auth, tags: { endpoint: "library" } }),
    { "library 200": (r) => r.status === 200 }
  );
  check(
    http.get(`${BASE}/shelves`, { headers: auth, tags: { endpoint: "shelves" } }),
    { "shelves 200": (r) => r.status === 200 }
  );

  if (WRITES) {
    const created = http.post(
      `${BASE}/library`,
      JSON.stringify({
        book: `k6 load test ${__VU}-${__ITER}`,
        author: "k6",
        status: "Yet to Buy",
        year: null,
      }),
      {
        headers: { ...auth, "Content-Type": "application/json" },
        tags: { endpoint: "library-write" },
      }
    );
    if (check(created, { "create 201": (r) => r.status === 201 })) {
      http.del(`${BASE}/library/${created.json("id")}`, null, {
        headers: auth,
        tags: { endpoint: "library-write" },
      });
    }
  }

  sleep(1);
}
