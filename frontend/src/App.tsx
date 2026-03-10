import { useEffect, useState } from "react";

type SearchResult = {
  id: string;
  name?: string;
  score: number;
  source: string;
  skills: string[];
  projects: string[];
};

type PersonSearchResult = {
  person_id: string;
  name?: string;
  department?: string;
  score: number;
  skills: string[];
  match_reason: string;
};

type FacultyDetailResult = {
  faculty_id: string;
  name: string;
  department?: string;
  email?: string;
  skills: string[];
  current_projects: string[];
  previous_projects: string[];
  previous_publications: string[];
};

type ProjectDetailResult = {
  project_id: string;
  project_name: string;
  description?: string;
  status?: string;
  progress?: number;
  tags: string[];
  faculty_names: string[];
  student_names: string[];
  related_papers: string[];
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

type GraphOverview = {
  counts: {
    students: number;
    faculty: number;
    projects: number;
    publications: number;
    skills: number;
    relationships: number;
  };
  connections: Array<{
    student_name: string;
    project_name: string;
    faculty_name: string;
    skills: string[];
    publications: string[];
  }>;
};

const apiBase = "http://localhost:8000";

export function App() {
  const [query, setQuery] = useState("Who is working on sustainable polymers?");
  const [facultyQuery, setFacultyQuery] = useState("faculty 1");
  const [projectQuery, setProjectQuery] = useState("sustainable polymers");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [personResults, setPersonResults] = useState<PersonSearchResult[]>([]);
  const [facultyResults, setFacultyResults] = useState<FacultyDetailResult[]>([]);
  const [projectResults, setProjectResults] = useState<ProjectDetailResult[]>([]);
  const [userId, setUserId] = useState("FAC-001");
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [graphOverview, setGraphOverview] = useState<GraphOverview | null>(null);
  const [loadingState, setLoadingState] = useState({
    researcher: false,
    person: false,
    faculty: false,
    project: false,
    recommend: false,
    hotspot: false,
    overview: false,
  });
  const [error, setError] = useState<string | null>(null);

  const runRequest = async <T,>(url: string, key: keyof typeof loadingState): Promise<T> => {
    setLoadingState((prev) => ({ ...prev, [key]: true }));
    setError(null);
    try {
      const res = await fetch(url);
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Request failed with ${res.status}`);
      }
      return (await res.json()) as T;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      throw err;
    } finally {
      setLoadingState((prev) => ({ ...prev, [key]: false }));
    }
  };

  const runSearch = async () => {
    const data = await runRequest<SearchResult[]>(
      `${apiBase}/search/researchers?query=${encodeURIComponent(query)}&limit=5`,
      "researcher"
    );
    setSearchResults(data);
  };

  const runPersonSearch = async () => {
    const data = await runRequest<PersonSearchResult[]>(
      `${apiBase}/search/people?query=${encodeURIComponent(query)}&top_k=5`,
      "person"
    );
    setPersonResults(data);
  };

  const runFacultySearch = async () => {
    const data = await runRequest<FacultyDetailResult[]>(
      `${apiBase}/search/faculty?query=${encodeURIComponent(facultyQuery)}&limit=5`,
      "faculty"
    );
    setFacultyResults(data);
  };

  const runProjectSearch = async () => {
    const data = await runRequest<ProjectDetailResult[]>(
      `${apiBase}/search/projects?query=${encodeURIComponent(projectQuery)}&limit=5`,
      "project"
    );
    setProjectResults(data);
  };

  const runRecommendations = async () => {
    const data = await runRequest<Recommendation[]>(
      `${apiBase}/recommend/${encodeURIComponent(userId)}`,
      "recommend"
    );
    setRecommendations(data);
  };

  const loadHotspots = async () => {
    const data = await runRequest<Hotspot[]>(`${apiBase}/analytics/hotspots?years=2`, "hotspot");
    setHotspots(data);
  };

  const loadGraphOverview = async () => {
    const data = await runRequest<GraphOverview>(`${apiBase}/graph/overview`, "overview");
    setGraphOverview(data);
  };

  useEffect(() => {
    loadGraphOverview().catch(() => undefined);
  }, []);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <h1 className="text-3xl font-semibold">Institutional Knowledge Intelligence Dashboard</h1>

        <section className="card">
          <h2 className="text-xl font-medium mb-3">Core Capabilities</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
            <div className="result-item">Semantic Search across people, skills, and projects</div>
            <div className="result-item">Collaborator Recommendation by expertise overlap</div>
            <div className="result-item">Innovation Trend Analysis via hotspot tags</div>
          </div>
        </section>

        <section className="card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xl font-medium">Knowledge Graph Connectivity</h2>
            <button className="button" onClick={loadGraphOverview} disabled={loadingState.overview}>
              {loadingState.overview ? "Loading..." : "Refresh Graph View"}
            </button>
          </div>
          {graphOverview && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-6 gap-2 text-sm mb-4">
                <div className="result-item">Students: {graphOverview.counts.students}</div>
                <div className="result-item">Faculty: {graphOverview.counts.faculty}</div>
                <div className="result-item">Projects: {graphOverview.counts.projects}</div>
                <div className="result-item">Publications: {graphOverview.counts.publications}</div>
                <div className="result-item">Skills: {graphOverview.counts.skills}</div>
                <div className="result-item">Relations: {graphOverview.counts.relationships}</div>
              </div>
              <ul className="space-y-2">
                {graphOverview.connections.map((conn, idx) => (
                  <li key={`${conn.student_name}-${conn.project_name}-${idx}`} className="result-item">
                    <div className="text-sm">
                      Student <span className="font-medium">{conn.student_name}</span> works on
                      <span className="font-medium"> {conn.project_name}</span> with Faculty
                      <span className="font-medium"> {conn.faculty_name}</span>
                    </div>
                    <div className="text-sm">Skills: {conn.skills.join(", ") || "-"}</div>
                    <div className="text-sm">Related Publications: {conn.publications.join(", ") || "-"}</div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>

        {error && (
          <section className="card border-red-700 bg-red-950/40">
            <p className="text-sm text-red-300">{error}</p>
          </section>
        )}

        <section className="card">
          <h2 className="text-xl font-medium mb-3">Researcher Search</h2>
          <div className="flex gap-3">
            <input className="input" value={query} onChange={(e) => setQuery(e.target.value)} />
            <button className="button" onClick={runSearch} disabled={loadingState.researcher}>
              {loadingState.researcher ? "Loading..." : "Search"}
            </button>
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
          <h2 className="text-xl font-medium mb-3">Person Semantic Search</h2>
          <div className="flex gap-3">
            <input className="input" value={query} onChange={(e) => setQuery(e.target.value)} />
            <button className="button" onClick={runPersonSearch} disabled={loadingState.person}>
              {loadingState.person ? "Loading..." : "Search People"}
            </button>
          </div>
          <ul className="mt-4 space-y-2">
            {personResults.map((r) => (
              <li key={r.person_id} className="result-item">
                <div className="font-medium">
                  {r.name} ({r.person_id})
                </div>
                <div className="text-sm">Department: {r.department || "-"}</div>
                <div className="text-sm">Score: {r.score.toFixed(3)}</div>
                <div className="text-sm">Skills: {r.skills.join(", ") || "-"}</div>
                <div className="text-sm">Reason: {r.match_reason}</div>
              </li>
            ))}
          </ul>
        </section>

        <section className="card">
          <h2 className="text-xl font-medium mb-3">Faculty Detailed View</h2>
          <div className="flex gap-3">
            <input
              className="input"
              value={facultyQuery}
              onChange={(e) => setFacultyQuery(e.target.value)}
              placeholder="Search faculty by name, skill, or department"
            />
            <button className="button" onClick={runFacultySearch} disabled={loadingState.faculty}>
              {loadingState.faculty ? "Loading..." : "Search Faculty"}
            </button>
          </div>
          <ul className="mt-4 space-y-2">
            {facultyResults.map((f) => (
              <li key={f.faculty_id} className="result-item">
                <div className="font-medium">{f.name} ({f.faculty_id})</div>
                <div className="text-sm">Department: {f.department || "-"}</div>
                <div className="text-sm">Email: {f.email || "-"}</div>
                <div className="text-sm">Skills: {f.skills.join(", ") || "-"}</div>
                <div className="text-sm">Current Work: {f.current_projects.join(", ") || "-"}</div>
                <div className="text-sm">Previous Work: {f.previous_projects.join(", ") || "-"}</div>
                <div className="text-sm">Publications: {f.previous_publications.join(", ") || "-"}</div>
              </li>
            ))}
          </ul>
        </section>

        <section className="card">
          <h2 className="text-xl font-medium mb-3">Project Detailed View</h2>
          <div className="flex gap-3">
            <input
              className="input"
              value={projectQuery}
              onChange={(e) => setProjectQuery(e.target.value)}
              placeholder="Is anyone working on this project..."
            />
            <button className="button" onClick={runProjectSearch} disabled={loadingState.project}>
              {loadingState.project ? "Loading..." : "Search Projects"}
            </button>
          </div>
          <ul className="mt-4 space-y-2">
            {projectResults.map((p) => (
              <li key={p.project_id} className="result-item">
                <div className="font-medium">{p.project_name} ({p.project_id})</div>
                <div className="text-sm">Status: {p.status || "-"} | Progress: {p.progress ?? "-"}%</div>
                <div className="text-sm">Description: {p.description || "-"}</div>
                <div className="text-sm">Faculty: {p.faculty_names.join(", ") || "-"}</div>
                <div className="text-sm">Students: {p.student_names.join(", ") || "-"}</div>
                <div className="text-sm">Tags: {p.tags.join(", ") || "-"}</div>
                <div className="text-sm">Completed Research Papers: {p.related_papers.join(", ") || "-"}</div>
              </li>
            ))}
          </ul>
        </section>

        <section className="card">
          <h2 className="text-xl font-medium mb-3">Collaborator Recommendations</h2>
          <div className="flex gap-3">
            <input className="input max-w-xs" value={userId} onChange={(e) => setUserId(e.target.value)} />
            <button className="button" onClick={runRecommendations} disabled={loadingState.recommend}>
              {loadingState.recommend ? "Loading..." : "Recommend"}
            </button>
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
          <button className="button" onClick={loadHotspots} disabled={loadingState.hotspot}>
            {loadingState.hotspot ? "Loading..." : "Load Hotspots"}
          </button>
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