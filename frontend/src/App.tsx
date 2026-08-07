/** Routes: the pitch at /, the tool at /app. */

import { Suspense, lazy } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { Landing } from "./routes/Landing";
import "./styles.css";

// deck.gl + MapLibre are ~1.8 MB. The landing page is the first thing a prospect loads, on a
// free-tier host that may have just cold-started, so it must not wait for the map engine.
const Studio = lazy(() => import("./routes/Studio").then((m) => ({ default: m.Studio })));

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route
          path="/app"
          element={
            <Suspense fallback={<Booting />}>
              <Studio />
            </Suspense>
          }
        >
        </Route>
        <Route path="*" element={<Landing />} />
      </Routes>
    </BrowserRouter>
  );
}

function Booting() {
  return (
    <div className="gate grid-ground">
      <div style={{ textAlign: "center" }}>
        <span className="spinner" />
        <div className="eyebrow" style={{ marginTop: "0.75rem" }}>
          Loading map engine
        </div>
      </div>
    </div>
  );
}
