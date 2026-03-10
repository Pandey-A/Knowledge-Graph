import { useEffect, useState } from "react";
import { 
  Activity, Brain, Search, Sparkles, Users, 
  GraduationCap, Network, RefreshCw, 
  FlaskConical, BookOpen, MapPin, ArrowRight
} from "lucide-react";

import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./components/ui/card";
import { Input } from "./components/ui/input";

// --- Types ---

type PersonSearchResult = {
  person_id: string;
  name?: string;
  department?: string;
  score: number;
  skills: string[];
  match_reason: string;
};

type QuickTopic = {
  label: string;
  query: string;
};

type ResearcherSearchResult = {
  id: string;
  name?: string;
  score: number;
  skills: string[];
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
  status?: string;
  progress?: number;
  faculty_names: string[];
};

type StudentSingleMatchResult = {
  match_type: "faculty" | "project";
  match_id: string;
  match_name: string;
  department?: string;
  score: number;
  reason: string;
  overlap_topics: string[];
  required_course?: string;
  project_status?: string;
  project_progress?: number;
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
  }>;
};

const apiBase = "http://localhost:8000";

const quickTopics: QuickTopic[] = [
  { label: "Sustainable Polymers", query: "sustainable polymers" },
  { label: "AI + Data Systems", query: "artificial intelligence data systems" },
  { label: "Robotics", query: "autonomous robotics" },
  { label: "Smart Grids", query: "smart grid optimization" },
  { label: "Structural Engineering", query: "civil structural monitoring" },
  { label: "Signal Processing", query: "electrical signal processing" },
];

const buildMockPersonResults = (rawQuery: string): PersonSearchResult[] => {
  const query = rawQuery.trim();
  const q = query.toLowerCase();

  const departmentCards = [
    {
      key: "cse",
      name: "Dr. Ananya Rao",
      department: "Computer Science and Engineering",
      skills: ["Machine Learning", "Distributed Systems", "Software Architecture"],
    },
    {
      key: "mech",
      name: "Dr. Vikram Desai",
      department: "Mechanical Engineering",
      skills: ["Robotics", "CAD/CAE", "Thermal Systems"],
    },
    {
      key: "electrical",
      name: "Dr. Sneha Iyer",
      department: "Electrical Engineering",
      skills: ["Power Systems", "Control Systems", "Smart Grids"],
    },
    {
      key: "civil",
      name: "Dr. Raghav Kulkarni",
      department: "Civil Engineering",
      skills: ["Structural Analysis", "Construction Materials", "Transport Engineering"],
    },
    {
      key: "chemical",
      name: "Dr. Priya Menon",
      department: "Chemical Engineering",
      skills: ["Sustainable Polymers", "Process Engineering", "Reaction Design"],
    },
  ];

  const ranked = departmentCards
    .map((card, idx) => {
      const keywordScore =
        Number(card.department.toLowerCase().includes(q)) +
        card.skills.filter((skill) => q && skill.toLowerCase().includes(q)).length;
      const looseScore =
        card.skills.filter((skill) => q && q.split(" ").some((part) => part && skill.toLowerCase().includes(part))).length;
      return { card, score: keywordScore * 0.3 + looseScore * 0.15 + (0.65 - idx * 0.05) };
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, 4)
    .map((item, idx) => ({
      person_id: `mock-person-${item.card.key}-${idx + 1}`,
      name: item.card.name,
      department: item.card.department,
      score: Math.max(0.4, item.score),
      skills: item.card.skills,
      match_reason: query
        ? `Interactive mock fallback for \"${query}\"`
        : "Interactive mock fallback",
    }));

  return ranked;
};

export function App() {
  const [activeTab, setActiveTab] = useState("semantic");
  const [query, setQuery] = useState("Who is working on sustainable polymers?");
  const [facultyQuery, setFacultyQuery] = useState("");
  const [projectQuery, setProjectQuery] = useState("");
  const [personResults, setPersonResults] = useState<PersonSearchResult[]>([]);
  const [facultyResults, setFacultyResults] = useState<FacultyDetailResult[]>([]);
  const [projectResults, setProjectResults] = useState<ProjectDetailResult[]>([]);
  const [studentTopic, setStudentTopic] = useState("sustainable polymers");
  const [studentCgpa, setStudentCgpa] = useState("8.5");
  const [studentCourse, setStudentCourse] = useState("Chemical Engineering");
  const [studentMatch, setStudentMatch] = useState<StudentSingleMatchResult | null>(null);
  const [studentMatchFacultyProfile, setStudentMatchFacultyProfile] = useState<FacultyDetailResult | null>(null);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [graphOverview, setGraphOverview] = useState<GraphOverview | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  
  const [loading, setLoading] = useState({
    person: false,
    faculty: false,
    project: false,
    studentMatch: false,
    facultyProfile: false,
    hotspot: false,
    overview: false,
  });

  const fetchFacultyProfileForMatch = async (match: StudentSingleMatchResult) => {
    if (match.match_type !== "faculty") {
      setStudentMatchFacultyProfile(null);
      return;
    }

    try {
      const data = await runRequest<FacultyDetailResult[]>(
        `${apiBase}/search/faculty?query=${encodeURIComponent(match.match_name)}&limit=5`,
        "facultyProfile"
      );

      const bestProfile =
        data.find((row) => row.faculty_id === match.match_id) ??
        data.find((row) => row.name.toLowerCase() === match.match_name.toLowerCase()) ??
        data[0] ??
        null;

      setStudentMatchFacultyProfile(bestProfile);
    } catch {
      setStudentMatchFacultyProfile(null);
    }
  };

  const runRequest = async <T,>(url: string, key: keyof typeof loading): Promise<T> => {
    setLoading((prev) => ({ ...prev, [key]: true }));
    try {
      setErrorMessage("");
      const res = await fetch(url);
      if (!res.ok) {
        const raw = await res.text();
        let detail = raw;
        try {
          const parsed = JSON.parse(raw);
          detail = parsed.detail ?? raw;
        } catch {
          detail = raw;
        }
        throw new Error(detail || `Request failed with status ${res.status}`);
      }
      return (await res.json()) as T;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Something went wrong while fetching data";
      setErrorMessage(message);
      throw error;
    } finally {
      setLoading((prev) => ({ ...prev, [key]: false }));
    }
  };

  const loadGraphOverview = async () => {
    try {
      const data = await runRequest<GraphOverview>(`${apiBase}/graph/overview`, "overview");
      setGraphOverview(data);
    } catch {
      setGraphOverview(null);
    }
  };

  const runPersonSearch = async () => {
    try {
      const data = await runRequest<PersonSearchResult[]>(`${apiBase}/search/people?query=${encodeURIComponent(query)}&top_k=5`, "person");
      if (data.length > 0) {
        setPersonResults(data);
        return;
      }

      const fallback = await runRequest<ResearcherSearchResult[]>(
        `${apiBase}/search/researchers?query=${encodeURIComponent(query)}&limit=5`,
        "person"
      );
      if (fallback.length > 0) {
        setPersonResults(
          fallback.map((row) => ({
            person_id: row.id,
            name: row.name,
            department: "",
            score: row.score,
            skills: row.skills ?? [],
            match_reason: "Keyword and graph relevance",
          }))
        );
        return;
      }

      setPersonResults(buildMockPersonResults(query));
    } catch {
      try {
        const fallback = await runRequest<ResearcherSearchResult[]>(
          `${apiBase}/search/researchers?query=${encodeURIComponent(query)}&limit=5`,
          "person"
        );
        if (fallback.length > 0) {
          setPersonResults(
            fallback.map((row) => ({
              person_id: row.id,
              name: row.name,
              department: "",
              score: row.score,
              skills: row.skills ?? [],
              match_reason: "Keyword and graph relevance",
            }))
          );
          return;
        }

        setPersonResults(buildMockPersonResults(query));
      } catch {
        setPersonResults(buildMockPersonResults(query));
      }
    }
  };

  const runQuickTopic = async (quickQuery: string) => {
    setQuery(quickQuery);
    try {
      const data = await runRequest<PersonSearchResult[]>(`${apiBase}/search/people?query=${encodeURIComponent(quickQuery)}&top_k=5`, "person");
      if (data.length > 0) {
        setPersonResults(data);
        return;
      }
      setPersonResults(buildMockPersonResults(quickQuery));
    } catch {
      setPersonResults(buildMockPersonResults(quickQuery));
    }
  };

  const runFacultySearch = async () => {
    try {
      const data = await runRequest<FacultyDetailResult[]>(`${apiBase}/search/faculty?query=${encodeURIComponent(facultyQuery)}&limit=5`, "faculty");
      setFacultyResults(data);
    } catch {
      setFacultyResults([]);
    }
  };

  const runProjectSearch = async () => {
    try {
      const data = await runRequest<ProjectDetailResult[]>(`${apiBase}/search/projects?query=${encodeURIComponent(projectQuery)}&limit=5`, "project");
      setProjectResults(data);
    } catch {
      setProjectResults([]);
    }
  };

  const runStudentMatch = async () => {
    const parsedCgpa = Number(studentCgpa);
    if (Number.isNaN(parsedCgpa) || parsedCgpa < 0 || parsedCgpa > 10) {
      setErrorMessage("Please enter CGPA between 0 and 10");
      return;
    }

    try {
      const data = await runRequest<StudentSingleMatchResult>(
        `${apiBase}/match/student?topic=${encodeURIComponent(studentTopic)}&cgpa=${encodeURIComponent(parsedCgpa.toString())}&course=${encodeURIComponent(studentCourse)}`,
        "studentMatch"
      );
      setStudentMatch(data);
      await fetchFacultyProfileForMatch(data);
    } catch {
      setStudentMatch(null);
      setStudentMatchFacultyProfile(null);
    }
  };

  const loadHotspots = async () => {
    try {
      const data = await runRequest<Hotspot[]>(`${apiBase}/analytics/hotspots?years=2`, "hotspot");
      setHotspots(data);
    } catch {
      setHotspots([]);
    }
  };

  useEffect(() => { loadGraphOverview(); }, []);

  return (
    <main className="min-h-screen bg-[#020617] text-slate-200 font-sans selection:bg-indigo-500/30">
      {/* Soft Background Glows */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-indigo-500/10 blur-[120px] rounded-full" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-blue-500/10 blur-[120px] rounded-full" />
      </div>

      <div className="relative mx-auto max-w-7xl p-6 md:p-10 space-y-10">
        
        {/* Header */}
        <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div>
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2.5 bg-indigo-600 rounded-xl shadow-lg shadow-indigo-500/20">
                <Brain className="h-7 w-7 text-white" />
              </div>
              <Badge className="border-indigo-500/30 text-indigo-400 bg-indigo-500/5 backdrop-blur-sm px-3 py-1">
                Institutional Graph v2.4
              </Badge>
            </div>
            <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight text-white leading-tight">
              Knowledge Intelligence
            </h1>
            <p className="mt-3 text-slate-400 max-w-xl text-lg font-medium">
              Map cross-departmental expertise and discover research synergy.
            </p>
          </div>
          <Button 
            onClick={loadGraphOverview} 
            disabled={loading.overview} 
            className="border border-slate-800 bg-slate-900/50 backdrop-blur hover:bg-slate-800 h-12 px-6"
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${loading.overview ? "animate-spin" : ""}`} />
            Sync Knowledge Base
          </Button>
        </header>

        {/* Stats Strip */}
        {graphOverview && (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {[
              { label: "Faculty", val: graphOverview.counts.faculty, icon: Users, color: "text-blue-400" },
              { label: "Students", val: graphOverview.counts.students, icon: GraduationCap, color: "text-emerald-400" },
              { label: "Projects", val: graphOverview.counts.projects, icon: FlaskConical, color: "text-amber-400" },
              { label: "Publications", val: graphOverview.counts.publications, icon: BookOpen, color: "text-purple-400" },
              { label: "Skills", val: graphOverview.counts.skills, icon: Activity, color: "text-indigo-400" },
              { label: "Nodes", val: graphOverview.counts.relationships, icon: Network, color: "text-rose-400" },
            ].map((s) => (
              <Card key={s.label} className="bg-slate-900/40 border-slate-800/50 backdrop-blur-sm shadow-xl">
                <CardContent className="p-4 flex flex-col items-center text-center">
                  <s.icon className={`h-5 w-5 mb-2 ${s.color}`} />
                  <span className="text-2xl font-bold text-white">{s.val.toLocaleString()}</span>
                  <span className="text-[10px] uppercase tracking-widest text-slate-500 font-bold mt-1">{s.label}</span>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Main Discovery Column */}
          <div className="lg:col-span-8 space-y-8">
            
            {/* Custom Styled Tabs */}
            <div className="bg-slate-900/50 p-1.5 rounded-xl border border-slate-800 inline-flex gap-1">
              {["semantic", "faculty", "projects"].map((t) => (
                <button
                  key={t}
                  onClick={() => setActiveTab(t)}
                  className={`px-6 py-2 rounded-lg text-sm font-semibold transition-all ${
                    activeTab === t ? "bg-indigo-600 text-white shadow-lg" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>

            {/* Tab Content: Semantic */}
            {activeTab === "semantic" && (
              <Card className="bg-slate-900/40 border-slate-800/50 backdrop-blur-md overflow-hidden animate-in fade-in slide-in-from-bottom-2">
                <div className="p-5 border-b border-slate-800/50 bg-slate-950/20 flex gap-3">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
                    <Input 
                      value={query} 
                      onChange={(e) => setQuery(e.target.value)} 
                      placeholder="e.g. Find experts in renewable energy..." 
                      className="bg-slate-950 border-slate-800 h-12 pl-10 focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                  <Button onClick={runPersonSearch} disabled={loading.person} className="bg-indigo-600 hover:bg-indigo-500 h-12 px-8 font-bold">
                    {loading.person ? "Thinking..." : "Discover"}
                  </Button>
                </div>
                <div className="px-6 pt-4">
                  <p className="text-[11px] uppercase tracking-wider text-slate-500 mb-2">Quick Explore</p>
                  <div className="flex flex-wrap gap-2">
                    {quickTopics.map((topic) => (
                      <button
                        key={topic.label}
                        onClick={() => runQuickTopic(topic.query)}
                        className="rounded-full border border-slate-700 bg-slate-950/70 px-3 py-1 text-[11px] text-slate-300 hover:border-indigo-500/50 hover:text-indigo-300 transition-all"
                      >
                        {topic.label}
                      </button>
                    ))}
                  </div>
                </div>
                {errorMessage && (
                  <div className="mx-6 mt-4 rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
                    {errorMessage}
                  </div>
                )}
                <div className="max-h-[500px] overflow-y-auto p-6 space-y-4">
                  {personResults.length > 0 && (
                    <div className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2">
                      <p className="text-xs text-slate-400">
                        {personResults.length} result{personResults.length > 1 ? "s" : ""} for "{query}"
                      </p>
                      <span className="text-[11px] text-indigo-300">Semantic + fallback ranking</span>
                    </div>
                  )}
                  {personResults.length === 0 && (
                    <div className="py-20 text-center text-slate-500 italic">Enter a query to explore the graph...</div>
                  )}
                  {personResults.map((r) => (
                    <div key={r.person_id} className="group p-5 rounded-xl border border-slate-800 bg-slate-950/40 hover:border-indigo-500/50 transition-all">
                      <div className="flex justify-between items-start mb-4">
                        <div>
                          <h3 className="font-bold text-xl text-white group-hover:text-indigo-300 transition-colors">{r.name}</h3>
                          <div className="flex items-center gap-2 mt-1 text-sm text-slate-400">
                            <MapPin className="h-3 w-3" /> {r.department}
                          </div>
                        </div>
                        <Badge className="bg-indigo-500/10 text-indigo-400 border-indigo-500/20 px-3 py-1">
                          {Math.round(r.score * 100)}% Match
                        </Badge>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {r.skills.map(s => <Badge key={s} className="bg-slate-800/50 text-slate-300 font-normal">{s}</Badge>)}
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {/* Other tabs can be added here with similar styling */}

            {/* Path Visualization Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {graphOverview?.connections.slice(0, 4).map((c, i) => (
                <div key={i} className="p-5 rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-950 shadow-inner">
                  <div className="flex items-center gap-3 text-sm">
                    <div className="w-8 h-8 rounded-full bg-emerald-500/10 flex items-center justify-center text-emerald-400 font-bold text-[10px]">ST</div>
                    <span className="font-medium text-slate-200">{c.student_name}</span>
                    <ArrowRight className="h-4 w-4 text-slate-600" />
                    <div className="w-8 h-8 rounded-full bg-indigo-500/10 flex items-center justify-center text-indigo-400 font-bold text-[10px]">PJ</div>
                    <span className="font-bold text-indigo-300">{c.project_name}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Sidebar Column */}
          <div className="lg:col-span-4 space-y-6">
            
            {/* AI Recommendations Card */}
            <Card className="bg-indigo-950/20 border-indigo-500/20 backdrop-blur-sm overflow-hidden">
              <div className="p-5 bg-indigo-600/10 border-b border-indigo-500/20">
                <CardTitle className="text-base flex items-center gap-2 text-indigo-300">
                  <Sparkles className="h-4 w-4" /> Student Best Match
                </CardTitle>
              </div>
              <CardContent className="p-5 space-y-5">
                <div className="space-y-3">
                  <Input
                    value={studentTopic}
                    onChange={(e) => setStudentTopic(e.target.value)}
                    placeholder="Research topic interest"
                    className="bg-slate-950 border-indigo-500/20 focus:border-indigo-500"
                  />
                  <Input
                    type="number"
                    step="0.1"
                    min="0"
                    max="10"
                    value={studentCgpa}
                    onChange={(e) => setStudentCgpa(e.target.value)}
                    placeholder="CGPA"
                    className="bg-slate-950 border-indigo-500/20 focus:border-indigo-500"
                  />
                  <Input
                    value={studentCourse}
                    onChange={(e) => setStudentCourse(e.target.value)}
                    placeholder="Course"
                    className="bg-slate-950 border-indigo-500/20 focus:border-indigo-500"
                  />
                  <Button onClick={runStudentMatch} disabled={loading.studentMatch} className="w-full bg-indigo-600 text-xs px-4">
                    {loading.studentMatch ? "Matching..." : "Find Best Match"}
                  </Button>
                </div>
                <div className="space-y-4">
                  {!studentMatch && (
                    <p className="text-xs text-slate-500 italic">Enter topic, CGPA and course to get one best professor/project match.</p>
                  )}
                  {studentMatch && (
                    <div className="rounded-xl border border-indigo-500/20 bg-slate-950/60 p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <Badge className="bg-indigo-500/10 text-indigo-300 border-indigo-500/20 capitalize">
                          {studentMatch.match_type}
                        </Badge>
                        <span className="text-xs font-semibold text-indigo-400">
                          {studentMatch.score.toFixed(0)} pts
                        </span>
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-slate-100">{studentMatch.match_name}</h3>
                        <p className="text-[11px] text-slate-400">{studentMatch.match_id}</p>
                      </div>
                      {studentMatch.department && (
                        <p className="text-xs text-slate-300">Department: {studentMatch.department}</p>
                      )}
                      <p className="text-xs text-slate-400">{studentMatch.reason}</p>
                      {studentMatch.overlap_topics.length > 0 && (
                        <div className="flex flex-wrap gap-2">
                          {studentMatch.overlap_topics.map((topic) => (
                            <Badge key={topic} className="bg-slate-800/50 text-slate-300 text-[10px] font-normal">{topic}</Badge>
                          ))}
                        </div>
                      )}
                      {studentMatch.match_type === "project" && (
                        <div className="text-xs text-slate-400 space-y-1">
                          {studentMatch.project_status && <p>Status: {studentMatch.project_status}</p>}
                          {studentMatch.project_progress != null && <p>Progress: {studentMatch.project_progress}%</p>}
                        </div>
                      )}

                      {studentMatch.match_type === "faculty" && loading.facultyProfile && (
                        <p className="text-xs text-indigo-300">Loading faculty profile...</p>
                      )}

                      {studentMatch.match_type === "faculty" && studentMatchFacultyProfile && (
                        <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3 space-y-3">
                          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">Faculty Profile</h4>
                          <p className="text-xs text-slate-300">
                            Email: {studentMatchFacultyProfile.email || "Not available"}
                          </p>
                          <div>
                            <p className="text-[11px] text-slate-400 mb-1">Current Work</p>
                            <div className="flex flex-wrap gap-2">
                              {studentMatchFacultyProfile.current_projects.length > 0 ? (
                                studentMatchFacultyProfile.current_projects.slice(0, 5).map((project) => (
                                  <Badge key={project} className="bg-indigo-500/10 text-indigo-300 border-indigo-500/20 text-[10px] font-normal">
                                    {project}
                                  </Badge>
                                ))
                              ) : (
                                <span className="text-xs text-slate-500">No active projects listed</span>
                              )}
                            </div>
                          </div>
                          <div>
                            <p className="text-[11px] text-slate-400 mb-1">Previous Work</p>
                            <div className="flex flex-wrap gap-2">
                              {studentMatchFacultyProfile.previous_projects.length > 0 ? (
                                studentMatchFacultyProfile.previous_projects.slice(0, 5).map((project) => (
                                  <Badge key={project} className="bg-slate-800/50 text-slate-300 text-[10px] font-normal">
                                    {project}
                                  </Badge>
                                ))
                              ) : (
                                <span className="text-xs text-slate-500">No previous projects listed</span>
                              )}
                            </div>
                          </div>
                          <div>
                            <p className="text-[11px] text-slate-400 mb-1">Publications</p>
                            <div className="flex flex-wrap gap-2">
                              {studentMatchFacultyProfile.previous_publications.length > 0 ? (
                                studentMatchFacultyProfile.previous_publications.slice(0, 5).map((publication) => (
                                  <Badge key={publication} className="bg-emerald-500/10 text-emerald-300 border-emerald-500/20 text-[10px] font-normal">
                                    {publication}
                                  </Badge>
                                ))
                              ) : (
                                <span className="text-xs text-slate-500">No publications listed</span>
                              )}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Hotspots Card */}
            <Card className="bg-slate-900/40 border-slate-800/50">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-base">Innovation Hotspots</CardTitle>
                <Activity className="h-4 w-4 text-emerald-400" />
              </CardHeader>
              <CardContent className="space-y-4">
                <Button onClick={loadHotspots} className="w-full border border-slate-800 h-9 text-xs font-bold uppercase tracking-wider bg-slate-950 text-slate-100 hover:bg-slate-900">
                  Update Trend Map
                </Button>
                {hotspots.map(h => (
                  <div key={h.tag} className="flex items-center justify-between p-3 rounded-lg bg-slate-950/50 border border-slate-800/50">
                    <div>
                      <span className="text-sm font-bold block text-slate-200">#{h.tag}</span>
                      <span className="text-[10px] text-slate-500 uppercase tracking-tighter">{h.publication_count} Papers</span>
                    </div>
                    <Badge className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20 text-[10px]">
                      +{h.momentum_score.toFixed(1)}
                    </Badge>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </main>
  );
}