// Smoke test (Phase 3, M8): 2 VUs, 1 minute, read-only non-AI endpoints.
// Confirms the script + auth work before running the real ramp (ramp.js).
//
//   TR_BASE_URL=https://<render-app>.onrender.com TR_JWT=<test-account-jwt> \
//     k6 run k6/smoke.js
//
// NEVER points at /summarise, /recommend, /library/query, or /curate — every
// request to those burns real OpenAI tokens and Langfuse units.
import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.TR_BASE_URL || "http://localhost:8000";
// JWT for a DEDICATED TEST ACCOUNT, passed via env var — never hard-coded.
const JWT = __ENV.TR_JWT || "";

export const options = {
  vus: 2,
  duration: "1m",
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<2000"],
  },
};

const authHeaders = { headers: { Authorization: `Bearer ${JWT}` } };

export default function () {
  check(http.get(`${BASE}/health`), { "health 200": (r) => r.status === 200 });
  check(http.get(`${BASE}/library`, authHeaders), {
    "library 200": (r) => r.status === 200,
  });
  check(http.get(`${BASE}/shelves`, authHeaders), {
    "shelves 200": (r) => r.status === 200,
  });
  sleep(1);
}
