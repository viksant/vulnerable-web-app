import { useState, useEffect } from "react";
import { ArrowLeft } from "lucide-react";
import apiClient from "../api/client";
import Container from "../components/ui/Container";
import Card from "../components/ui/Card";
import Input from "../components/ui/Input";
import Button from "../components/ui/Button";
import Badge from "../components/ui/Badge";

/**
 * Neo-Brutalist support panel.
 * List of tickets. Click opens ticket detail with chat-like messages.
 */
export default function SupportPanel() {
  const [tickets, setTickets] = useState([]);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [messages, setMessages] = useState([]);
  const [reply, setReply] = useState("");
  const [isInternal, setIsInternal] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchTickets();
  }, []);

  async function fetchTickets() {
    setIsLoading(true);
    try {
      const response = await apiClient.get("/support/tickets");
      setTickets(response.data || []);
    } catch {
      setTickets([]);
    } finally {
      setIsLoading(false);
    }
  }

  async function openTicket(ticket) {
    setSelectedTicket(ticket);
    try {
      const response = await apiClient.get(`/support/tickets/${ticket.id}/messages`);
      setMessages(response.data || []);
    } catch {
      setMessages([]);
    }
  }

  async function handleSendReply(e) {
    e.preventDefault();
    if (!reply.trim()) return;
    try {
      await apiClient.post(`/support/tickets/${selectedTicket.id}/messages`, {
        body: reply,
        is_internal: isInternal,
      });
      setReply("");
      setIsInternal(false);
      // Refresh messages
      openTicket(selectedTicket);
    } catch {
      // Error logged by interceptor
    }
  }

  if (isLoading) {
    return (
      <main className="min-h-screen bg-neo-bg py-16">
        <Container>
          <p className="animate-bounce-slow text-center font-black text-3xl uppercase">
            LOADING...
          </p>
        </Container>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-neo-bg py-16">
      <Container>
        <h1 className="mb-8 font-black text-5xl uppercase tracking-tight">
          SUPPORT PANEL
        </h1>

        {selectedTicket ? (
          /* Ticket detail */
          <div>
            <button
              onClick={() => setSelectedTicket(null)}
              className="mb-6 inline-flex items-center gap-2 font-bold uppercase transition-all duration-100 hover:border-4 hover:border-black hover:bg-neo-accent hover:px-2 hover:shadow-neo-sm"
            >
              <ArrowLeft className="h-5 w-5" strokeWidth={3} />
              BACK TO TICKETS
            </button>

            <Card header={`TICKET #${selectedTicket.id}`} headerColor="bg-neo-muted" shadow="shadow-neo-lg">
              <div className="p-6">
                <h2 className="mb-4 font-black text-2xl uppercase">
                  {selectedTicket.subject || "No Subject"}
                </h2>

                {/* Messages */}
                <div className="flex flex-col gap-4">
                  {messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`border-4 border-black p-4 ${
                        msg.is_internal
                          ? "bg-neo-muted"
                          : "bg-white"
                      }`}
                    >
                      <div className="mb-2 flex items-center gap-2">
                        <Badge variant="dark">{msg.author || "System"}</Badge>
                        {msg.is_internal && (
                          <Badge variant="muted">INTERNAL</Badge>
                        )}
                        <span className="ml-auto text-sm font-bold text-black/60">
                          {msg.created_at
                            ? new Date(msg.created_at).toLocaleString()
                            : ""}
                        </span>
                      </div>
                      <p className="font-bold text-lg">{msg.body}</p>
                    </div>
                  ))}
                </div>

                {/* Reply form */}
                <form onSubmit={handleSendReply} className="mt-6 flex flex-col gap-4">
                  <Input
                    type="textarea"
                    placeholder="Type your reply..."
                    value={reply}
                    onChange={(e) => setReply(e.target.value)}
                    required
                  />
                  <div className="flex items-center gap-4">
                    <label className="flex items-center gap-2 font-bold">
                      <input
                        type="checkbox"
                        checked={isInternal}
                        onChange={(e) => setIsInternal(e.target.checked)}
                        className="h-6 w-6 border-4 border-black"
                      />
                      Internal note
                    </label>
                    <Button type="submit" variant="primary">
                      SEND
                    </Button>
                  </div>
                </form>
              </div>
            </Card>
          </div>
        ) : (
          /* Ticket list */
          <div className="flex flex-col gap-4">
            {tickets.length === 0 ? (
              <p className="py-16 text-center font-black text-2xl uppercase text-black/30">
                NO TICKETS
              </p>
            ) : (
              tickets.map((ticket) => (
                <Card
                  key={ticket.id}
                  hoverable
                  shadow="shadow-neo-sm"
                  onClick={() => openTicket(ticket)}
                >
                  <div className="flex items-center gap-4 p-4">
                    <Badge variant="dark">#{ticket.id}</Badge>
                    <span className="flex-1 font-black text-lg uppercase">
                      {ticket.subject || "No Subject"}
                    </span>
                    <Badge variant={ticket.status === "open" ? "secondary" : "muted"}>
                      {(ticket.status || "open").toUpperCase()}
                    </Badge>
                  </div>
                </Card>
              ))
            )}
          </div>
        )}
      </Container>
    </main>
  );
}
