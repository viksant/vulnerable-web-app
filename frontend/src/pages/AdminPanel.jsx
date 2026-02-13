import { useState, useEffect } from "react";
import apiClient from "../api/client";
import Container from "../components/ui/Container";
import Card from "../components/ui/Card";
import Input from "../components/ui/Input";
import Button from "../components/ui/Button";
import Badge from "../components/ui/Badge";

const TABS = ["USERS", "CONFIG", "REPORTS", "LOGS"];

/**
 * Neo-Brutalist admin panel.
 * Tabs: Users table, Config JSON, Reports generator, Log viewer.
 */
export default function AdminPanel() {
  const [activeTab, setActiveTab] = useState(0);
  const [users, setUsers] = useState([]);
  const [config, setConfig] = useState({});
  const [logContent, setLogContent] = useState("");
  const [logFilename, setLogFilename] = useState("app.log");
  const [reportTemplate, setReportTemplate] = useState("sales");
  const [reportDate, setReportDate] = useState("");
  const [reportResult, setReportResult] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (activeTab === 0) fetchUsers();
    if (activeTab === 1) fetchConfig();
  }, [activeTab]);

  async function fetchUsers() {
    setIsLoading(true);
    try {
      const response = await apiClient.get("/admin/users");
      setUsers(response.data || []);
    } catch {
      setUsers([]);
    } finally {
      setIsLoading(false);
    }
  }

  async function fetchConfig() {
    try {
      const response = await apiClient.get("/admin/config");
      setConfig(response.data || {});
    } catch {
      setConfig({});
    }
  }

  async function fetchLogs() {
    try {
      const response = await apiClient.get(`/admin/logs/${logFilename}`);
      setLogContent(
        typeof response.data === "string"
          ? response.data
          : JSON.stringify(response.data, null, 2),
      );
    } catch (err) {
      setLogContent(err.response?.data?.detail || "Failed to fetch logs");
    }
  }

  async function generateReport(e) {
    e.preventDefault();
    setReportResult("");
    try {
      const response = await apiClient.post("/admin/reports", {
        template: reportTemplate,
        date: reportDate,
      });
      setReportResult(JSON.stringify(response.data, null, 2));
    } catch (err) {
      setReportResult(err.response?.data?.detail || "Failed to generate report");
    }
  }

  return (
    <main className="min-h-screen bg-neo-bg py-16">
      <Container>
        <h1 className="mb-8 font-black text-5xl uppercase tracking-tight">
          ADMIN PANEL
        </h1>

        {/* Tabs */}
        <div className="mb-8 flex flex-wrap gap-2">
          {TABS.map((tab, i) => (
            <Button
              key={tab}
              variant={activeTab === i ? "dark" : "outline"}
              size="sm"
              onClick={() => setActiveTab(i)}
            >
              {tab}
            </Button>
          ))}
        </div>

        {/* Users */}
        {activeTab === 0 && (
          <div className="overflow-x-auto">
            <table className="w-full border-4 border-black">
              <thead>
                <tr className="bg-neo-secondary">
                  <th className="border-4 border-black p-3 text-left font-black uppercase">
                    ID
                  </th>
                  <th className="border-4 border-black p-3 text-left font-black uppercase">
                    USERNAME
                  </th>
                  <th className="border-4 border-black p-3 text-left font-black uppercase">
                    EMAIL
                  </th>
                  <th className="border-4 border-black p-3 text-left font-black uppercase">
                    ROLE
                  </th>
                  <th className="border-4 border-black p-3 text-left font-black uppercase">
                    STATUS
                  </th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="bg-white">
                    <td className="border-4 border-black p-3 font-bold">
                      {u.id}
                    </td>
                    <td className="border-4 border-black p-3 font-bold">
                      {u.username}
                    </td>
                    <td className="border-4 border-black p-3 font-bold">
                      {u.email}
                    </td>
                    <td className="border-4 border-black p-3">
                      <Badge variant={u.role === "admin" ? "accent" : "muted"}>
                        {(u.role || "customer").toUpperCase()}
                      </Badge>
                    </td>
                    <td className="border-4 border-black p-3">
                      <Badge variant={u.is_active ? "secondary" : "dark"}>
                        {u.is_active ? "ACTIVE" : "DISABLED"}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Config */}
        {activeTab === 1 && (
          <Card header="APP CONFIG" headerColor="bg-neo-muted" shadow="shadow-neo-lg">
            <pre className="overflow-x-auto p-6 font-mono text-lg font-bold leading-relaxed">
              {JSON.stringify(config, null, 2)}
            </pre>
          </Card>
        )}

        {/* Reports */}
        {activeTab === 2 && (
          <div className="flex flex-col gap-6">
            <Card header="GENERATE REPORT" headerColor="bg-neo-secondary" shadow="shadow-neo-lg">
              <form onSubmit={generateReport} className="flex flex-col gap-4 p-6">
                <div>
                  <label className="mb-1 block text-sm font-bold uppercase tracking-widest">
                    Template
                  </label>
                  <select
                    value={reportTemplate}
                    onChange={(e) => setReportTemplate(e.target.value)}
                    className="h-14 w-full border-4 border-black bg-white px-4 font-bold text-lg focus:bg-neo-secondary focus:outline-none"
                  >
                    <option value="sales">Sales Report</option>
                    <option value="users">Users Report</option>
                    <option value="inventory">Inventory Report</option>
                    <option value="security">Security Audit</option>
                  </select>
                </div>
                <Input
                  label="Date"
                  type="date"
                  value={reportDate}
                  onChange={(e) => setReportDate(e.target.value)}
                />
                <Button type="submit" variant="primary">
                  GENERATE
                </Button>
              </form>
            </Card>

            {reportResult && (
              <Card shadow="shadow-neo-sm">
                <pre className="overflow-x-auto p-6 font-mono text-lg font-bold">
                  {reportResult}
                </pre>
              </Card>
            )}
          </div>
        )}

        {/* Logs */}
        {activeTab === 3 && (
          <div className="flex flex-col gap-6">
            <div className="flex gap-0">
              <input
                type="text"
                value={logFilename}
                onChange={(e) => setLogFilename(e.target.value)}
                placeholder="app.log"
                className="h-14 flex-1 border-4 border-r-0 border-black bg-white px-4 font-bold text-lg placeholder:text-black/40 focus:bg-neo-secondary focus:outline-none"
              />
              <Button
                variant="dark"
                className="h-14 border-4 border-black"
                onClick={fetchLogs}
              >
                VIEW LOGS
              </Button>
            </div>

            <Card shadow="shadow-neo-lg">
              <pre className="max-h-96 overflow-auto p-6 font-mono text-sm font-bold leading-relaxed">
                {logContent || "Enter a filename and click VIEW LOGS"}
              </pre>
            </Card>
          </div>
        )}
      </Container>
    </main>
  );
}
