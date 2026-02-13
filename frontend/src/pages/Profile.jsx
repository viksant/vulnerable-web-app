import { useState, useEffect } from "react";
import apiClient from "../api/client";
import { getCurrentUser } from "../utils/auth";
import Container from "../components/ui/Container";
import Card from "../components/ui/Card";
import Input from "../components/ui/Input";
import Button from "../components/ui/Button";
import Divider from "../components/ui/Divider";

/**
 * Neo-Brutalist profile page with sections for personal info, email, and password.
 */
export default function Profile() {
  const user = getCurrentUser();
  const [profile, setProfile] = useState({ username: "", email: "" });
  const [newEmail, setNewEmail] = useState("");
  const [passwords, setPasswords] = useState({ current: "", new_password: "", confirm: "" });
  const [message, setMessage] = useState("");

  useEffect(() => {
    fetchProfile();
  }, []);

  async function fetchProfile() {
    try {
      const response = await apiClient.get("/auth/me");
      setProfile(response.data);
      setNewEmail(response.data.email || "");
    } catch {
      // Use decoded JWT data as fallback
      if (user) {
        setProfile({ username: user.username || "", email: user.email || "" });
        setNewEmail(user.email || "");
      }
    }
  }

  async function handleUpdateEmail(e) {
    e.preventDefault();
    setMessage("");
    try {
      await apiClient.put("/auth/email", { email: newEmail });
      setMessage("Email updated");
      fetchProfile();
    } catch (err) {
      setMessage(err.response?.data?.detail || "Failed to update email");
    }
  }

  async function handleUpdatePassword(e) {
    e.preventDefault();
    setMessage("");
    if (passwords.new_password !== passwords.confirm) {
      setMessage("Passwords do not match");
      return;
    }
    try {
      await apiClient.put("/auth/password", {
        current_password: passwords.current,
        new_password: passwords.new_password,
      });
      setPasswords({ current: "", new_password: "", confirm: "" });
      setMessage("Password updated");
    } catch (err) {
      setMessage(err.response?.data?.detail || "Failed to update password");
    }
  }

  return (
    <main className="min-h-screen bg-neo-bg py-16">
      <Container className="max-w-2xl">
        <h1 className="mb-8 font-black text-5xl uppercase tracking-tight">
          PROFILE
        </h1>

        {message && (
          <div className="mb-6 border-4 border-black bg-neo-secondary p-4 font-bold">
            {message}
          </div>
        )}

        <Card shadow="shadow-neo-lg">
          {/* Personal Info */}
          <div className="p-6">
            <h2 className="mb-4 font-black text-2xl uppercase">
              PERSONAL INFO
            </h2>
            <div className="flex flex-col gap-4">
              <Input label="Username" value={profile.username} disabled />
              <Input label="Email" value={profile.email} disabled />
              <Input label="Role" value={user?.role || "customer"} disabled />
            </div>
          </div>

          <Divider />

          {/* Change Email */}
          <form onSubmit={handleUpdateEmail} className="p-6">
            <h2 className="mb-4 font-black text-2xl uppercase">
              CHANGE EMAIL
            </h2>
            <div className="flex flex-col gap-4">
              <Input
                label="New Email"
                type="email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                required
              />
              <Button type="submit" variant="secondary">
                UPDATE EMAIL
              </Button>
            </div>
          </form>

          <Divider />

          {/* Change Password */}
          <form onSubmit={handleUpdatePassword} className="p-6">
            <h2 className="mb-4 font-black text-2xl uppercase">
              CHANGE PASSWORD
            </h2>
            <div className="flex flex-col gap-4">
              <Input
                label="Current Password"
                type="password"
                value={passwords.current}
                onChange={(e) =>
                  setPasswords((p) => ({ ...p, current: e.target.value }))
                }
                required
              />
              <Input
                label="New Password"
                type="password"
                value={passwords.new_password}
                onChange={(e) =>
                  setPasswords((p) => ({ ...p, new_password: e.target.value }))
                }
                required
              />
              <Input
                label="Confirm Password"
                type="password"
                value={passwords.confirm}
                onChange={(e) =>
                  setPasswords((p) => ({ ...p, confirm: e.target.value }))
                }
                required
              />
              <Button type="submit" variant="secondary">
                UPDATE PASSWORD
              </Button>
            </div>
          </form>
        </Card>
      </Container>
    </main>
  );
}
