"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";

interface CalendarConnection {
  id: string;
  provider: "google" | "microsoft";
  status: "connected" | "disconnected" | "error" | "expired";
  account_email?: string;
  calendar_id?: string;
  calendar_name?: string;
  created_at?: string;
  last_synced_at?: string;
}

interface CalendarOption {
  id: string;
  name: string;
  is_primary?: boolean;
  access_role?: string;
}

export default function CalendarSettingsPage() {
  const [mounted, setMounted] = useState<boolean>(false);
  const [connections, setConnections] = useState<CalendarConnection[]>([]);
  const [googleCalendars, setGoogleCalendars] = useState<CalendarOption[]>([]);
  const [microsoftCalendars, setMicrosoftCalendars] = useState<CalendarOption[]>([]);
  const [selectedGoogleCal, setSelectedGoogleCal] = useState<string>("");
  const [selectedMicrosoftCal, setSelectedMicrosoftCal] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [syncing, setSyncing] = useState<boolean>(false);
  const [notification, setNotification] = useState<{ type: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    setMounted(true);
    fetchConnections();
  }, []);

  const getHeaders = () => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    const clinicId = typeof window !== "undefined" ? localStorage.getItem("clinic_id") : "clinic-kds-001";
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-Clinic-ID": clinicId || "clinic-kds-001",
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    return headers;
  };

  const fetchConnections = async () => {
    setLoading(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/v1/calendar/connections`, {
        headers: getHeaders(),
      });
      if (res.ok) {
        const data: CalendarConnection[] = await res.json();
        setConnections(data);

        for (const conn of data) {
          if (conn.status === "connected") {
            if (conn.provider === "google") {
              setSelectedGoogleCal(conn.calendar_id || "");
              fetchCalendarList("google");
            } else if (conn.provider === "microsoft") {
              setSelectedMicrosoftCal(conn.calendar_id || "");
              fetchCalendarList("microsoft");
            }
          }
        }
      }
    } catch (err: any) {
      console.error("Failed to fetch calendar connections:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchCalendarList = async (provider: "google" | "microsoft") => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/v1/calendar/calendars?provider=${provider}`, {
        headers: getHeaders(),
      });
      if (res.ok) {
        const calendars: CalendarOption[] = await res.json();
        if (provider === "google") {
          setGoogleCalendars(calendars);
        } else {
          setMicrosoftCalendars(calendars);
        }
      }
    } catch (err) {
      console.error(`Failed to fetch ${provider} calendars:`, err);
    }
  };

  const handleConnect = async (provider: "google" | "microsoft") => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/v1/calendar/${provider}/connect`, {
        headers: getHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.auth_url) {
          window.location.href = data.auth_url;
        }
      } else {
        const err = await res.json();
        setNotification({ type: "error", message: err.detail || `Failed to connect ${provider} calendar.` });
      }
    } catch (err) {
      setNotification({ type: "error", message: `Connection request failed for ${provider}.` });
    }
  };

  const handleDisconnect = async (provider: "google" | "microsoft") => {
    if (!confirm(`Are you sure you want to disconnect ${provider === "google" ? "Google Calendar" : "Microsoft Outlook"}?`)) {
      return;
    }
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/v1/calendar/${provider}/disconnect`, {
        method: "POST",
        headers: getHeaders(),
      });
      if (res.ok) {
        setNotification({ type: "success", message: `${provider === "google" ? "Google Calendar" : "Microsoft Outlook"} disconnected successfully.` });
        fetchConnections();
      } else {
        const err = await res.json();
        setNotification({ type: "error", message: err.detail || "Failed to disconnect." });
      }
    } catch (err) {
      setNotification({ type: "error", message: "Failed to disconnect calendar." });
    }
  };

  const handleSelectCalendar = async (provider: "google" | "microsoft", calendarId: string) => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/v1/calendar/select`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({
          provider,
          calendar_id: calendarId,
        }),
      });
      if (res.ok) {
        setNotification({ type: "success", message: "Active calendar updated successfully." });
        if (provider === "google") setSelectedGoogleCal(calendarId);
        else setSelectedMicrosoftCal(calendarId);
        fetchConnections();
      } else {
        const err = await res.json();
        setNotification({ type: "error", message: err.detail || "Failed to update calendar selection." });
      }
    } catch (err) {
      setNotification({ type: "error", message: "Failed to select calendar." });
    }
  };

  const handleManualSync = async () => {
    setSyncing(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/v1/calendar/sync`, {
        method: "POST",
        headers: getHeaders(),
      });
      if (res.ok) {
        const result = await res.json();
        setNotification({
          type: "success",
          message: `Calendar sync completed. Synced: ${result.synced_count ?? 0}, Failed: ${result.failed_count ?? 0}`,
        });
        fetchConnections();
      } else {
        const err = await res.json();
        setNotification({ type: "error", message: err.detail || "Sync failed." });
      }
    } catch (err) {
      setNotification({ type: "error", message: "Calendar synchronization request failed." });
    } finally {
      setSyncing(false);
    }
  };

  const googleConn = connections.find((c) => c.provider === "google");
  const microsoftConn = connections.find((c) => c.provider === "microsoft");

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-16">
          <div className="flex items-center gap-6">
            <Link href="/" className="flex items-center gap-2">
              <span className="w-8 h-8 rounded-lg bg-emerald-600 text-white font-bold flex items-center justify-center text-sm shadow-xs">
                AI
              </span>
              <span className="font-bold text-base text-slate-900 hidden sm:inline">
                Clinic CRM
              </span>
            </Link>

            <nav className="flex items-center gap-1 sm:gap-2">
              <Link
                href="/dashboard"
                className="px-3 py-1.5 text-xs font-medium rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition"
              >
                Dashboard
              </Link>
              <Link
                href="/appointments"
                className="px-3 py-1.5 text-xs font-medium rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition"
              >
                Appointments
              </Link>
              <Link
                href="/settings/calendar"
                className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200"
              >
                Calendar Sync
              </Link>
            </nav>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleManualSync}
              disabled={syncing}
              className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow-xs transition flex items-center gap-1.5"
            >
              <svg className={`w-3.5 h-3.5 ${syncing ? "animate-spin" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              {syncing ? "Syncing..." : "Sync All Calendars"}
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Banner */}
        <div>
          <div className="inline-flex items-center gap-2 px-2.5 py-0.5 bg-emerald-50 text-emerald-700 text-xs font-medium rounded-full mb-2 border border-emerald-200">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            CHUNK 12 — Calendar Integration & Synchronization
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Calendar Integration Settings
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Connect clinic Google Calendar and Microsoft Outlook to automatically synchronize scheduled, updated, and cancelled patient appointments.
          </p>
        </div>

        {/* Notifications */}
        {notification && (
          <div
            className={`p-4 rounded-xl text-xs font-medium border flex items-center justify-between ${
              notification.type === "success"
                ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                : "bg-rose-50 text-rose-800 border-rose-200"
            }`}
          >
            <span>{notification.message}</span>
            <button
              onClick={() => setNotification(null)}
              className="text-slate-400 hover:text-slate-600 font-bold ml-4"
            >
              &times;
            </button>
          </div>
        )}

        {/* Provider Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Card 1: Google Calendar */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-6 space-y-5 flex flex-col justify-between">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-blue-50 border border-blue-100 flex items-center justify-center font-bold text-blue-600 text-sm">
                    G
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-slate-900">Google Calendar</h2>
                    <p className="text-xs text-slate-500">Google Workspace & Gmail</p>
                  </div>
                </div>
                <span
                  className={`px-2.5 py-0.5 text-xs font-semibold rounded-full border capitalize ${
                    googleConn?.status === "connected"
                      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                      : "bg-slate-100 text-slate-600 border-slate-200"
                  }`}
                >
                  {googleConn?.status || "Disconnected"}
                </span>
              </div>

              {googleConn?.status === "connected" ? (
                <div className="space-y-3 pt-2">
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 space-y-1">
                    <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                      Connected Account
                    </div>
                    <div className="text-xs font-bold text-slate-800">
                      {googleConn.account_email || "Active Account"}
                    </div>
                    {googleConn.last_synced_at && (
                      <div className="text-[11px] text-slate-500">
                        Last synced: {new Date(googleConn.last_synced_at).toLocaleString()}
                      </div>
                    )}
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Active Calendar for Bookings
                    </label>
                    <select
                      value={selectedGoogleCal}
                      onChange={(e) => handleSelectCalendar("google", e.target.value)}
                      className="w-full text-xs font-medium bg-white border border-slate-300 rounded-lg p-2 text-slate-800 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                    >
                      <option value="primary">Primary Calendar</option>
                      {googleCalendars.map((cal) => (
                        <option key={cal.id} value={cal.id}>
                          {cal.name} {cal.is_primary ? "(Primary)" : ""}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-slate-600">
                  Connect your Google account to automatically push confirmed clinic bookings, updates, and cancellations to your clinic calendar.
                </p>
              )}
            </div>

            <div className="pt-4 border-t border-slate-100 flex items-center justify-end gap-2">
              {googleConn?.status === "connected" ? (
                <button
                  onClick={() => handleDisconnect("google")}
                  className="px-3 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-lg text-xs font-semibold transition"
                >
                  Disconnect Google
                </button>
              ) : (
                <button
                  onClick={() => handleConnect("google")}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-xs transition"
                >
                  Connect Google Calendar
                </button>
              )}
            </div>
          </div>

          {/* Card 2: Microsoft Outlook Calendar */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-6 space-y-5 flex flex-col justify-between">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-sky-50 border border-sky-100 flex items-center justify-center font-bold text-sky-600 text-sm">
                    M
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-slate-900">Microsoft Outlook</h2>
                    <p className="text-xs text-slate-500">Microsoft 365 & Outlook.com</p>
                  </div>
                </div>
                <span
                  className={`px-2.5 py-0.5 text-xs font-semibold rounded-full border capitalize ${
                    microsoftConn?.status === "connected"
                      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                      : "bg-slate-100 text-slate-600 border-slate-200"
                  }`}
                >
                  {microsoftConn?.status || "Disconnected"}
                </span>
              </div>

              {microsoftConn?.status === "connected" ? (
                <div className="space-y-3 pt-2">
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 space-y-1">
                    <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                      Connected Account
                    </div>
                    <div className="text-xs font-bold text-slate-800">
                      {microsoftConn.account_email || "Active Account"}
                    </div>
                    {microsoftConn.last_synced_at && (
                      <div className="text-[11px] text-slate-500">
                        Last synced: {new Date(microsoftConn.last_synced_at).toLocaleString()}
                      </div>
                    )}
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Active Calendar for Bookings
                    </label>
                    <select
                      value={selectedMicrosoftCal}
                      onChange={(e) => handleSelectCalendar("microsoft", e.target.value)}
                      className="w-full text-xs font-medium bg-white border border-slate-300 rounded-lg p-2 text-slate-800 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                    >
                      <option value="primary">Primary Calendar</option>
                      {microsoftCalendars.map((cal) => (
                        <option key={cal.id} value={cal.id}>
                          {cal.name} {cal.is_primary ? "(Primary)" : ""}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-slate-600">
                  Connect your Microsoft 365 or Outlook account to sync appointments in real time with clinic staff calendars.
                </p>
              )}
            </div>

            <div className="pt-4 border-t border-slate-100 flex items-center justify-end gap-2">
              {microsoftConn?.status === "connected" ? (
                <button
                  onClick={() => handleDisconnect("microsoft")}
                  className="px-3 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-lg text-xs font-semibold transition"
                >
                  Disconnect Microsoft
                </button>
              ) : (
                <button
                  onClick={() => handleConnect("microsoft")}
                  className="px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white rounded-lg text-xs font-semibold shadow-xs transition"
                >
                  Connect Outlook Calendar
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Informational Guidelines */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-3">
          <h3 className="text-sm font-bold text-slate-900">Synchronization Invariants</h3>
          <ul className="text-xs text-slate-600 space-y-2 list-disc list-inside">
            <li><strong>CRM Authoritative:</strong> Internal clinic database remains the single source of truth for all bookings and patient states.</li>
            <li><strong>Idempotent Operations:</strong> Changes to appointment times or notes update existing external events without duplicating entries.</li>
            <li><strong>Tenant Isolation:</strong> OAuth tokens and calendar credentials are encrypted at rest with AES-256 and never shared across clinics.</li>
            <li><strong>Automatic Sync:</strong> All confirmed, updated, or cancelled bookings are queued for background synchronization every 60 seconds.</li>
          </ul>
        </div>
      </main>
    </div>
  );
}

