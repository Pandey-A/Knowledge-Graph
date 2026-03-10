import { useState } from "react";

type SearchResult = {
  id: string;
  name?: string;
  score: number;
  source: string;
  skills: string[];
  projects: string[];
};

type Recommendation = {
  candidate_id: string;
  candidate_name: string;
  score: number;
  shared_skills: string[];
  shared_interests: string[];
};

type Hotspot = {
  tag: string;
  publication_count: number;
  project_count: number;
  momentum_score: number;
};

const apiBase = "http://localhost:8000";

export function App() {
  const [query, setQuery] = useState("Who is working on sustainable polymers?");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [userId, setUserId] = useState("FAC-001");
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);

  const runSearch = async () => {
    const res = await fetch(`${apiBase}/search/researchers?query=${encodeURIComponent(query)}`);
    setSearchResults(await res.json());
  };

  const runRecommendations = async () => {
    const res = await fetch(`${apiBase}/recommend/${encodeURIComponent(userId)}`);
    setRecommendations(await res.json());
  };

  const loadHotspots = async () => {
    const res = await fetch(`${apiBase}/analytics/hotspots?years=2`);
    setHotspots(await res.json());
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <h1 className="text-3xl font-semibold">Institutional Knowledge Intelligence Dashboard</h1>

        <section className="card">
          <h2 className="text-xl font-medium mb-3">Semantic Search</h2>
          <div className="flex gap-3">
            <input className="input" value={query} onChange={(e) => setQuery(e.target.value)} />
            <button className="button" onClick={runSearch}>Search</button>
          </div>
          <ul className="mt-4 space-y-2">
            {searchResults.map((r) => (
              <li key={r.id} className="result-item">
                <div className="font-medium">{r.name} ({r.id})</div>
                <div className="text-sm">Score: {r.score.toFixed(3)} | Source: {r.source}</div>
                <div className="text-sm">Skills: {r.skills.join(", ") || "-"}</div>
                <div className="text-sm">Projects: {r.projects.join(", ") || "-"}</div>
              </li>
            ))}
          </ul>
        </section>

        <section className="card">
          <h2 className="text-xl font-medium mb-3">Collaborator Recommendations</h2>
          <div className="flex gap-3">
            <input className="input max-w-xs" value={userId} onChange={(e) => setUserId(e.target.value)} />
            <button className="button" onClick={runRecommendations}>Recommend</button>
          </div>
          <ul className="mt-4 space-y-2">
            {recommendations.map((r) => (
              <li key={r.candidate_id} className="result-item">
                <div className="font-medium">{r.candidate_name} ({r.candidate_id})</div>
                <div className="text-sm">Score: {r.score.toFixed(3)}</div>
                <div className="text-sm">Shared skills: {r.shared_skills.join(", ") || "-"}</div>
                <div className="text-sm">Shared interests: {r.shared_interests.join(", ") || "-"}</div>
              </li>
            ))}
          </ul>
        </section>

        <section className="card">
          <h2 className="text-xl font-medium mb-3">Innovation Hotspots (Last 2 Years)</h2>
          <button className="button" onClick={loadHotspots}>Load Hotspots</button>
          <ul className="mt-4 space-y-2">
            {hotspots.map((h) => (
              <li key={h.tag} className="result-item">
                <div className="font-medium">{h.tag}</div>
                <div className="text-sm">
                  Publications: {h.publication_count} | Projects: {h.project_count} | Momentum: {h.momentum_score.toFixed(2)}
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </main>
  );
}