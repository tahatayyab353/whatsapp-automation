"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";

interface DashboardMetrics {
  total_leads: number;
  open_conversations: number;
  pending_handoffs: number;
  today_appointments: number;
  confirmed_appointments_today: number;
  completed_appointments_today: number;
  new_leads_today: number;
}

interface AppointmentItem {
  id: string;
  lead_name?: string;
  lead_phone?: string;
  title: string;
  scheduled_at: string;
  duration_minutes: number;
  status: "requested" | "confirmed" | "cancelled" | "completed" | "no_show" | "rescheduled";
  notes?: string;
}

interface HandoffItem {
  id: string;
  conversation_id: string;
  lead_name?: string;
  lead_phone?: string;
  reason: string;
  status: "pending" | "assigned" | "resolved" | "cancelled";
  notes?: string;
  requested_at: string;
  assigned_to_name?: string;
}

interface ConversationItem {
  id: string;
  lead_name?: string;
  lead_phone?: string;
  channel: string;
  status: string;
  last_message_at?: string;
  last_message_preview?: string;
}

interface LeadItem {
  id: string;
  full_name?: string;
  phone: string;
  email?: string;
  status: string;
  service_interest?: string;
  created_at: string;
}

interface DashboardData {
  clinic_id: string;
  clinic_name: string;
  timezone: string;
  metrics: DashboardMetrics;
  today_appointments: AppointmentItem[];
  pending_handoffs: HandoffItem[];
  recent_conversations: ConversationItem[];
  recent_leads: LeadItem[];
}

// Initial default data for fallback or initial render
const DEFAULT_DATA: DashboardData = {
  clinic_id: "clinic-kds-001",
  clinic_name: "Karachi Dental Studio",
  timezone: "Asia/Karachi",
  metrics: {
    total_leads: 12,
    open_conversations: 4,
    pending_handoffs: 2,
    today_appointments: 3,
    confirmed_appointments_today: 2,
    completed_appointments_today: 1,
    new_leads_today: 3,
  },
  today_appointments: [
    {
      id: "appt-1",
      lead_name: "Farhan Qureshi",
      lead_phone: "+92 300 5554433",
      title: "Scaling & Polishing",
      scheduled_at: new Date(Date.now() + 2 * 3600 * 1000).toISOString(),
      duration_minutes: 30,
      status: "confirmed",
      notes: "First time visit",
    },
    {
      id: "appt-2",
      lead_name: "Sara Khan",
      lead_phone: "+92 321 9876543",
      title: "Invisalign Assessment",
      scheduled_at: new Date(Date.now() + 4 * 3600 * 1000).toISOString(),
      duration_minutes: 45,
      status: "requested",
      notes: "Inquired about 3D scan",
    },
    {
      id: "appt-3",
      lead_name: "Bilal Siddiqui",
      lead_phone: "+92 333 1112233",
      title: "Root Canal Followup",
      scheduled_at: new Date(Date.now() - 1 * 3600 * 1000).toISOString(),
      duration_minutes: 30,
      status: "completed",
    },
  ],
  pending_handoffs: [
    {
      id: "hnd-1",
      conversation_id: "conv-1",
      lead_name: "Farhan Qureshi",
      lead_phone: "+92 300 5554433",
      reason: "customer_requested_human",
      status: "pending",
      notes: "Customer asked to speak directly with receptionist",
      requested_at: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
    },
    {
      id: "hnd-2",
      conversation_id: "conv-2",
      lead_name: "Zainab Ali",
      lead_phone: "+92 300 1122334",
      reason: "ai_uncertain",
      status: "assigned",
      assigned_to_name: "Ali Staff",
      notes: "Complex questions on surgical insurance coverage",
      requested_at: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
    },
  ],
  recent_conversations: [
    {
      id: "conv-1",
      lead_name: "Farhan Qureshi",
      lead_phone: "+92 300 5554433",
      channel: "whatsapp",
      status: "human_required",
      last_message_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
      last_message_preview: "Can someone call me regarding appointment charges?",
    },
    {
      id: "conv-2",
      lead_name: "Zainab Ali",
      lead_phone: "+92 300 1122334",
      channel: "whatsapp",
      status: "human_required",
      last_message_at: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
      last_message_preview: "Our scaling at Karachi Dental Studio is PKR 4,500.",
    },
    {
      id: "conv-3",
      lead_name: "Sara Khan",
      lead_phone: "+92 321 9876543",
      channel: "whatsapp",
      status: "open",
      last_message_at: new Date(Date.now() - 50 * 60 * 1000).toISOString(),
      last_message_preview: "Thanks, see you tomorrow.",
    },
  ],
  recent_leads: [
    {
      id: "lead-1",
      full_name: "Farhan Qureshi",
      phone: "+92 300 5554433",
      email: "farhan@example.com",
      status: "appointment_requested",
      service_interest: "Scaling & Polishing",
      created_at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
    },
    {
      id: "lead-2",
      full_name: "Sara Khan",
      phone: "+92 321 9876543",
      email: "sara@gmail.com",
      status: "qualified",
      service_interest: "Invisalign",
      created_at: new Date(Date.now() - 5 * 3600 * 1000).toISOString(),
    },
    {
      id: "lead-3",
      full_name: "Bilal Siddiqui",
      phone: "+92 333 1112233",
      status: "contacted",
      service_interest: "Root Canal",
      created_at: new Date(Date.now() - 24 * 3600 * 1000).toISOString(),
    },
  ],
};

export default function DashboardPage() {
  const [mounted, setMounted] = useState<boolean>(false);
  const [data, setData] = useState<DashboardData>(DEFAULT_DATA);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setMounted(true);
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    setLoading(true);
    setError(null);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const clinicId = typeof window !== "undefined" ? localStorage.getItem("clinic_id") : null;

      let res;
      if (token && clinicId) {
        res = await fetch(`${apiUrl}/api/v1/dashboard/summary`, {
          headers: {
            Authorization: `Bearer ${token}`,
            "X-Clinic-ID": clinicId,
          },
        });
      } else {
        res = await fetch(`${apiUrl}/api/v1/dashboard/live-preview`);
      }

      if (res && res.ok) {
        const json = await res.json();
        setData({
          clinic_id: json.clinic_id || "demo-clinic",
          clinic_name: json.clinic_name || "Demo Dental Clinic",
          timezone: json.timezone || "Asia/Karachi",
          metrics: {
            total_leads: json.metrics?.total_leads ?? 0,
            open_conversations: json.metrics?.open_conversations ?? 0,
            pending_handoffs: json.metrics?.pending_handoffs ?? 0,
            today_appointments: json.metrics?.today_appointments ?? 0,
            confirmed_appointments_today: json.metrics?.confirmed_appointments_today ?? 0,
            completed_appointments_today: json.metrics?.completed_appointments_today ?? 0,
            new_leads_today: json.metrics?.new_leads_today ?? 0,
          },
          today_appointments: json.today_appointments || [],
          pending_handoffs: json.pending_handoffs || json.active_handoffs || [],
          recent_conversations: json.recent_conversations || [],
          recent_leads: json.recent_leads || [],
        });
      }
    } catch (err: any) {
      console.error("Failed to fetch live dashboard data:", err);
    } finally {
      setLoading(false);
    }
  };

  // Status badge styling helper
  const getStatusBadge = (status: string) => {
    switch (status) {
      case "confirmed":
      case "completed":
      case "qualified":
        return "bg-emerald-50 text-emerald-700 border-emerald-200";
      case "requested":
      case "appointment_requested":
      case "pending":
        return "bg-amber-50 text-amber-700 border-amber-200";
      case "human_required":
      case "assigned":
        return "bg-purple-50 text-purple-700 border-purple-200";
      case "cancelled":
        return "bg-rose-50 text-rose-700 border-rose-200";
      case "no_show":
        return "bg-slate-100 text-slate-700 border-slate-300";
      default:
        return "bg-slate-100 text-slate-700 border-slate-200";
    }
  };

  // Appointment actions
  const handleApptAction = (id: string, newStatus: AppointmentItem["status"]) => {
    setData((prev) => ({
      ...prev,
      today_appointments: prev.today_appointments.map((a) =>
        a.id === id ? { ...a, status: newStatus } : a
      ),
    }));
  };

  // Handoff actions
  const handleHandoffAction = (id: string, newStatus: HandoffItem["status"]) => {
    setData((prev) => ({
      ...prev,
      pending_handoffs: prev.pending_handoffs.map((h) =>
        h.id === id ? { ...h, status: newStatus, assigned_to_name: newStatus === "assigned" ? "You" : h.assigned_to_name } : h
      ),
      metrics: {
        ...prev.metrics,
        pending_handoffs: Math.max(0, prev.metrics.pending_handoffs - (newStatus === "resolved" ? 1 : 0)),
      },
    }));
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Top Navigation Bar */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-16">
          <div className="flex items-center gap-6">
            <Link href="/" className="flex items-center gap-2">
              <span className="w-8 h-8 rounded-lg bg-emerald-600 text-white font-bold flex items-center justify-center text-sm shadow-xs">
                AI
              </span>
              <span className="font-bold text-base text-slate-900 hidden sm:inline">
                {data.clinic_name}
              </span>
            </Link>

            <nav className="flex items-center gap-1 sm:gap-2">
              <Link
                href="/dashboard"
                className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200"
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
                className="px-3 py-1.5 text-xs font-medium rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition"
              >
                Calendar Sync
              </Link>
            </nav>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-right hidden sm:block">
              <div className="text-xs font-semibold text-slate-800">{data.clinic_name}</div>
              <div className="text-[11px] text-slate-500">{data.timezone}</div>
            </div>
            <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-slate-100 text-slate-700 border border-slate-200">
              Staff Portal
            </span>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Page Title & Status Banner */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-2.5 py-0.5 bg-emerald-50 text-emerald-700 text-xs font-medium rounded-full mb-2 border border-emerald-200">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              Clinic Operations Live
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Operational Overview
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Live activity feed, today&apos;s schedule, and patient inquiries.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                setLoading(true);
                setTimeout(() => setLoading(false), 300);
              }}
              className="px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-medium shadow-xs transition"
            >
              {loading ? "Refreshing..." : "Refresh Feed"}
            </button>
            <Link
              href="/appointments"
              className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-xs transition"
            >
              + New Appointment
            </Link>
          </div>
        </div>

        {/* 1. Summary Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Card 1: Total Leads */}
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Total Leads
              </span>
              <span className="text-xs font-medium text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">
                +{data.metrics.new_leads_today} today
              </span>
            </div>
            <div className="mt-3">
              <div className="text-2xl font-bold text-slate-900">{data.metrics.total_leads}</div>
              <p className="text-xs text-slate-500 mt-0.5">Active patient inquiries</p>
            </div>
          </div>

          {/* Card 2: Open Conversations */}
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Open Chats
              </span>
              <span className="text-xs font-medium text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">
                WhatsApp
              </span>
            </div>
            <div className="mt-3">
              <div className="text-2xl font-bold text-slate-900">{data.metrics.open_conversations}</div>
              <p className="text-xs text-slate-500 mt-0.5">Active conversation threads</p>
            </div>
          </div>

          {/* Card 3: Pending Handoffs */}
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Staff Escalations
              </span>
              {data.metrics.pending_handoffs > 0 ? (
                <span className="text-xs font-bold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200">
                  Needs Attention
                </span>
              ) : (
                <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                  All Clear
                </span>
              )}
            </div>
            <div className="mt-3">
              <div className="text-2xl font-bold text-slate-900">{data.metrics.pending_handoffs}</div>
              <p className="text-xs text-slate-500 mt-0.5">Awaiting human pickup</p>
            </div>
          </div>

          {/* Card 4: Today's Appointments */}
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Today&apos;s Visits
              </span>
              <span className="text-xs font-medium text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">
                {data.metrics.confirmed_appointments_today} Confirmed
              </span>
            </div>
            <div className="mt-3">
              <div className="text-2xl font-bold text-slate-900">{data.metrics.today_appointments}</div>
              <p className="text-xs text-slate-500 mt-0.5">
                {data.metrics.completed_appointments_today} completed so far
              </p>
            </div>
          </div>
        </div>

        {/* 2. Main Two-Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column (2 Cols): Today's Appointments & Recent Conversations */}
          <div className="lg:col-span-2 space-y-8">
            {/* Section A: Today's Appointments */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-bold text-slate-900">Today&apos;s Appointments</h2>
                  <p className="text-xs text-slate-500">Scheduled visits for today</p>
                </div>
                <Link
                  href="/appointments"
                  className="text-xs font-semibold text-emerald-600 hover:text-emerald-700"
                >
                  View All &rarr;
                </Link>
              </div>

              <div className="divide-y divide-slate-100">
                {data.today_appointments.length === 0 ? (
                  <div className="p-8 text-center text-xs text-slate-500">
                    No appointments scheduled for today.
                  </div>
                ) : (
                  data.today_appointments.map((appt) => {
                    const dateObj = new Date(appt.scheduled_at);
                    return (
                      <div key={appt.id} className="p-4 hover:bg-slate-50/50 transition">
                        <div className="flex items-start justify-between gap-4">
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-sm text-slate-900">
                                {appt.lead_name || "Patient"}
                              </span>
                              <span className="text-xs text-slate-500">{appt.lead_phone}</span>
                            </div>
                            <div className="text-xs text-slate-700 font-medium">{appt.title}</div>
                            {appt.notes && (
                              <div className="text-xs text-slate-500 italic">{appt.notes}</div>
                            )}
                          </div>

                          <div className="text-right space-y-2">
                            <div className="flex items-center justify-end gap-2">
                              <span
                                className={`px-2 py-0.5 text-xs font-semibold rounded-full border capitalize ${getStatusBadge(
                                  appt.status
                                )}`}
                              >
                                {appt.status.replace("_", " ")}
                              </span>
                              <span suppressHydrationWarning className="text-xs font-semibold text-slate-700">
                                {mounted
                                  ? dateObj.toLocaleTimeString("en-PK", {
                                      hour: "2-digit",
                                      minute: "2-digit",
                                    })
                                  : "Loading..."}
                              </span>
                            </div>

                            {/* Quick Actions */}
                            <div className="flex items-center justify-end gap-1.5 pt-1">
                              {appt.status === "requested" && (
                                <button
                                  onClick={() => handleApptAction(appt.id, "confirmed")}
                                  className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-[11px] font-semibold transition"
                                >
                                  Confirm
                                </button>
                              )}
                              {appt.status === "confirmed" && (
                                <button
                                  onClick={() => handleApptAction(appt.id, "completed")}
                                  className="px-2.5 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-[11px] font-semibold transition"
                                >
                                  Complete
                                </button>
                              )}
                              {appt.status !== "cancelled" && appt.status !== "completed" && (
                                <button
                                  onClick={() => handleApptAction(appt.id, "cancelled")}
                                  className="px-2.5 py-1 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded text-[11px] font-semibold transition"
                                >
                                  Cancel
                                </button>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* Section B: Recent Conversations */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-bold text-slate-900">Recent WhatsApp Conversations</h2>
                  <p className="text-xs text-slate-500">Live incoming threads from customers</p>
                </div>
              </div>

              <div className="divide-y divide-slate-100">
                {data.recent_conversations.length === 0 ? (
                  <div className="p-8 text-center text-xs text-slate-500">
                    No recent conversations recorded.
                  </div>
                ) : (
                  data.recent_conversations.map((c) => (
                    <div key={c.id} className="p-4 hover:bg-slate-50/50 transition">
                      <div className="flex items-start justify-between gap-2">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-sm text-slate-900">
                              {c.lead_name || "Unknown Patient"}
                            </span>
                            <span className="text-xs text-slate-500">{c.lead_phone}</span>
                            <span
                              className={`px-2 py-0.5 text-[10px] font-semibold rounded-full border capitalize ${getStatusBadge(
                                c.status
                              )}`}
                            >
                              {c.status.replace("_", " ")}
                            </span>
                          </div>
                          <p className="text-xs text-slate-600 line-clamp-1">
                            {c.last_message_preview || "No message history"}
                          </p>
                        </div>

                        <div className="text-[11px] text-slate-400 whitespace-nowrap">
                          {c.last_message_at
                            ? new Date(c.last_message_at).toLocaleTimeString([], {
                                hour: "2-digit",
                                minute: "2-digit",
                              })
                            : ""}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Right Column (1 Col): Human Handoff Queue & Recent Leads */}
          <div className="space-y-8">
            {/* Section C: Human Handoff Queue */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-bold text-slate-900">Handoff Queue</h2>
                  <p className="text-xs text-slate-500">Escalations needing staff reply</p>
                </div>
                {data.metrics.pending_handoffs > 0 && (
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse"></span>
                )}
              </div>

              <div className="divide-y divide-slate-100">
                {data.pending_handoffs.length === 0 ? (
                  <div className="p-8 text-center text-xs text-slate-500">
                    No active handoffs in queue.
                  </div>
                ) : (
                  data.pending_handoffs.map((h) => (
                    <div key={h.id} className="p-4 space-y-2 hover:bg-slate-50/50 transition">
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="font-semibold text-sm text-slate-900">
                            {h.lead_name || "Patient"}
                          </div>
                          <div className="text-xs text-slate-500">{h.lead_phone}</div>
                        </div>
                        <span
                          className={`px-2 py-0.5 text-[10px] font-semibold rounded-full border capitalize ${getStatusBadge(
                            h.status
                          )}`}
                        >
                          {h.status}
                        </span>
                      </div>

                      <div className="text-xs text-slate-700 bg-slate-50 p-2 rounded border border-slate-100">
                        <strong className="text-slate-900">Reason:</strong> {h.reason.replace(/_/g, " ")}
                        {h.notes && <div className="text-slate-500 text-[11px] mt-0.5">{h.notes}</div>}
                      </div>

                      <div className="flex items-center justify-between pt-1">
                        <span className="text-[11px] text-slate-400">
                          {h.assigned_to_name ? `Assigned: ${h.assigned_to_name}` : "Unassigned"}
                        </span>
                        <div className="flex items-center gap-1.5">
                          {h.status === "pending" && (
                            <button
                              onClick={() => handleHandoffAction(h.id, "assigned")}
                              className="px-2.5 py-1 bg-purple-600 hover:bg-purple-700 text-white rounded text-[11px] font-semibold transition"
                            >
                              Claim
                            </button>
                          )}
                          {h.status === "assigned" && (
                            <button
                              onClick={() => handleHandoffAction(h.id, "resolved")}
                              className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-[11px] font-semibold transition"
                            >
                              Resolve
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Section D: Recent Leads */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-bold text-slate-900">Recent Patient Leads</h2>
                  <p className="text-xs text-slate-500">Captured and qualified via AI</p>
                </div>
              </div>

              <div className="divide-y divide-slate-100">
                {data.recent_leads.length === 0 ? (
                  <div className="p-8 text-center text-xs text-slate-500">
                    No leads registered yet.
                  </div>
                ) : (
                  data.recent_leads.map((l) => (
                    <div key={l.id} className="p-4 space-y-1 hover:bg-slate-50/50 transition">
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="font-semibold text-sm text-slate-900">
                            {l.full_name || "New Lead"}
                          </div>
                          <div className="text-xs text-slate-500">{l.phone}</div>
                        </div>
                        <span
                          className={`px-2 py-0.5 text-[10px] font-semibold rounded-full border capitalize ${getStatusBadge(
                            l.status
                          )}`}
                        >
                          {l.status.replace("_", " ")}
                        </span>
                      </div>
                      {l.service_interest && (
                        <div className="text-xs text-slate-600 font-medium">
                          Interest: {l.service_interest}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

