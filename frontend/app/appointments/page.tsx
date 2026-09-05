"use client";

import React, { useState } from "react";

interface ReminderStatus {
  reminder_type: "APPOINTMENT_24H" | "APPOINTMENT_2H";
  status: "pending" | "processing" | "sent" | "failed" | "cancelled";
  scheduled_for: string;
  sent_at?: string;
  failed_at?: string;
  attempts?: number;
}

interface AppointmentItem {
  id: string;
  lead_name: string;
  phone: string;
  title: string;
  description?: string;
  scheduled_at: string;
  duration_minutes: number;
  timezone: string;
  status: "requested" | "confirmed" | "cancelled" | "completed" | "no_show" | "rescheduled";
  notes?: string;
  reminders?: ReminderStatus[];
}

const SAMPLE_APPOINTMENTS: AppointmentItem[] = [
  {
    id: "appt-001",
    lead_name: "Farhan Qureshi",
    phone: "+92 300 5554433",
    title: "Scaling & Polishing",
    description: "Routine checkup and teeth cleaning requested via WhatsApp",
    scheduled_at: "2026-09-06T10:30:00Z",
    duration_minutes: 30,
    timezone: "Asia/Karachi",
    status: "requested",
    notes: "Patient prefers morning slot.",
    reminders: [
      {
        reminder_type: "APPOINTMENT_24H",
        status: "pending",
        scheduled_for: "2026-09-05T10:30:00Z",
        attempts: 0,
      },
      {
        reminder_type: "APPOINTMENT_2H",
        status: "pending",
        scheduled_for: "2026-09-06T08:30:00Z",
        attempts: 0,
      },
    ],
  },
  {
    id: "appt-002",
    lead_name: "Sara Khan",
    phone: "+92 321 9876543",
    title: "Invisalign Consultation",
    description: "Aligner assessment and 3D scan consultation",
    scheduled_at: "2026-09-06T14:00:00Z",
    duration_minutes: 45,
    timezone: "Asia/Karachi",
    status: "confirmed",
    notes: "Confirmed by Dr. Tariq.",
    reminders: [
      {
        reminder_type: "APPOINTMENT_24H",
        status: "sent",
        scheduled_for: "2026-09-05T14:00:00Z",
        sent_at: "2026-09-05T14:00:05Z",
        attempts: 1,
      },
      {
        reminder_type: "APPOINTMENT_2H",
        status: "pending",
        scheduled_for: "2026-09-06T12:00:00Z",
        attempts: 0,
      },
    ],
  },
  {
    id: "appt-003",
    lead_name: "Bilal Siddiqui",
    phone: "+92 333 1112233",
    title: "Dental Veneers Checkup",
    description: "Hollywood smile assessment",
    scheduled_at: "2026-09-07T11:00:00Z",
    duration_minutes: 30,
    timezone: "Asia/Karachi",
    status: "completed",
    notes: "Treatment plan provided.",
    reminders: [
      {
        reminder_type: "APPOINTMENT_24H",
        status: "sent",
        scheduled_for: "2026-09-06T11:00:00Z",
        sent_at: "2026-09-06T11:00:02Z",
        attempts: 1,
      },
      {
        reminder_type: "APPOINTMENT_2H",
        status: "sent",
        scheduled_for: "2026-09-07T09:00:00Z",
        sent_at: "2026-09-07T09:00:04Z",
        attempts: 1,
      },
    ],
  },
];



export default function AppointmentsPage() {
  const [mounted, setMounted] = useState<boolean>(false);
  const [appointments, setAppointments] = useState<AppointmentItem[]>(SAMPLE_APPOINTMENTS);
  const [selectedAppt, setSelectedAppt] = useState<AppointmentItem | null>(SAMPLE_APPOINTMENTS[0]);
  const [statusFilter, setStatusFilter] = useState<string>("all");

  React.useEffect(() => {
    setMounted(true);
  }, []);

  const handleStatusChange = (id: string, newStatus: AppointmentItem["status"]) => {
    setAppointments((prev) =>
      prev.map((a) => (a.id === id ? { ...a, status: newStatus } : a))
    );
    if (selectedAppt && selectedAppt.id === id) {
      setSelectedAppt((prev) => (prev ? { ...prev, status: newStatus } : null));
    }
  };

  const filteredAppointments = appointments.filter((appt) => {
    if (statusFilter === "all") return true;
    return appt.status === statusFilter;
  });

  const getStatusBadge = (status: AppointmentItem["status"]) => {
    switch (status) {
      case "requested":
        return "bg-amber-50 text-amber-700 border-amber-200";
      case "confirmed":
        return "bg-blue-50 text-blue-700 border-blue-200";
      case "completed":
        return "bg-emerald-50 text-emerald-700 border-emerald-200";
      case "cancelled":
        return "bg-rose-50 text-rose-700 border-rose-200";
      case "no_show":
        return "bg-slate-100 text-slate-700 border-slate-300";
      default:
        return "bg-gray-100 text-gray-700 border-gray-200";
    }
  };

  const getReminderBadge = (status?: string) => {
    switch (status) {
      case "sent":
        return "bg-emerald-100 text-emerald-800 border-emerald-300";
      case "pending":
        return "bg-amber-100 text-amber-800 border-amber-300";
      case "processing":
        return "bg-blue-100 text-blue-800 border-blue-300";
      case "cancelled":
        return "bg-slate-100 text-slate-600 border-slate-300";
      case "failed":
        return "bg-rose-100 text-rose-800 border-rose-300";
      default:
        return "bg-gray-100 text-gray-600 border-gray-200";
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          <div>
            <div className="inline-flex items-center gap-2 px-2.5 py-0.5 bg-emerald-50 text-emerald-700 text-xs font-medium rounded-full mb-2 border border-emerald-200">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              CHUNK 9 — Appointment System Active
              CHUNK 11 — Notifications & Reminders Active
            </div>
            <h1 className="text-2xl font-bold text-slate-900">Clinic Appointments</h1>
            <p className="text-sm text-slate-500">
              Manage patient bookings, AI booking requests, and confirmations.
              Manage patient bookings, AI booking requests, and automated WhatsApp reminders.
            </p>
          </div>

          {/* Status filter */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-xs font-medium bg-slate-50 border border-slate-300 rounded-lg px-3 py-1.5 text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              <option value="all">All Appointments</option>
              <option value="requested">Requested</option>
              <option value="confirmed">Confirmed</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
              <option value="no_show">No-Show</option>
            </select>
          </div>
        </div>

        {/* Main Grid: List & Detail View */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Appointment List (2 cols) */}
          <div className="md:col-span-2 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-800">
                Scheduled Appointments ({filteredAppointments.length})
              </h2>
            </div>
            <div className="divide-y divide-slate-100 max-h-[600px] overflow-y-auto">
              {filteredAppointments.length === 0 ? (
                <div className="p-8 text-center text-sm text-slate-500">
                  No appointments found for status filter &quot;{statusFilter}&quot;.
                </div>
              ) : (
                filteredAppointments.map((appt) => {
                  const isSelected = selectedAppt?.id === appt.id;
                  const dateObj = new Date(appt.scheduled_at);
                  return (
                    <div
                      key={appt.id}
                      onClick={() => setSelectedAppt(appt)}
                      className={`p-4 cursor-pointer transition-colors ${
                        isSelected ? "bg-emerald-50/60 border-l-4 border-emerald-600" : "hover:bg-slate-50"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="font-semibold text-sm text-slate-900">{appt.lead_name}</div>
                          <div className="text-xs text-slate-500">{appt.phone}</div>
                          <div className="text-xs font-medium text-slate-700 mt-1">{appt.title}</div>
                        </div>
                        <div className="text-right">
                          <span
                            className={`inline-block px-2 py-0.5 text-xs font-semibold rounded-full border capitalize ${getStatusBadge(
                              appt.status
                            )}`}
                          >
                            {appt.status.replace("_", " ")}
                          </span>
                          <div suppressHydrationWarning className="text-xs text-slate-500 mt-1">
                            {mounted ? (
                              <>
                                {dateObj.toLocaleDateString("en-PK", {
                                  month: "short",
                                  day: "numeric",
                                })}{" "}
                                at{" "}
                                {dateObj.toLocaleTimeString("en-PK", {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}
                              </>
                            ) : (
                              "Loading..."
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

          {/* Appointment Detail & Actions (1 col) */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-4">
            <h2 className="text-sm font-bold text-slate-800 border-b border-slate-100 pb-3">
              Appointment Details
            </h2>

            {selectedAppt ? (
              <div className="space-y-4">
                <div>
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Patient</span>
                  <div className="text-base font-bold text-slate-900">{selectedAppt.lead_name}</div>
                  <div className="text-xs text-slate-500">{selectedAppt.phone}</div>
                </div>

                <div>
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Procedure / Purpose</span>
                  <div className="text-sm font-medium text-slate-800">{selectedAppt.title}</div>
                  {selectedAppt.description && (
                    <div className="text-xs text-slate-500 mt-0.5">{selectedAppt.description}</div>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="font-semibold text-slate-400 uppercase tracking-wider block">Date & Time</span>
                    <span suppressHydrationWarning className="text-slate-800 font-medium">
                      {mounted ? new Date(selectedAppt.scheduled_at).toLocaleDateString() : "Loading..."}
                    </span>
                  </div>
                  <div>
                    <span className="font-semibold text-slate-400 uppercase tracking-wider block">Duration</span>
                    <span className="text-slate-800 font-medium">{selectedAppt.duration_minutes} mins</span>
                  </div>
                </div>

                <div>
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Status</span>
                  <span
                    className={`inline-block px-2.5 py-1 text-xs font-semibold rounded-full border mt-1 capitalize ${getStatusBadge(
                      selectedAppt.status
                    )}`}
                  >
                    {selectedAppt.status.replace("_", " ")}
                  </span>
                </div>

                {selectedAppt.notes && (
                  <div>
                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Staff Notes</span>
                    <div className="text-xs text-slate-600 bg-slate-50 p-2.5 rounded-lg border border-slate-100 mt-1">
                      {selectedAppt.notes}
                    </div>
                  </div>
                )}

                {/* WhatsApp Reminders (Chunk 11) */}
                <div className="pt-2 border-t border-slate-100 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      WhatsApp Reminders
                    </span>
                    <span className="text-[10px] bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded font-medium border border-emerald-200">
                      Auto
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {/* 24H Reminder */}
                    <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-semibold text-slate-700 text-[11px]">24h Reminder</span>
                        {(() => {
                          const r24 = selectedAppt.reminders?.find((r) => r.reminder_type === "APPOINTMENT_24H");
                          const rStatus = r24 ? r24.status : "pending";
                          return (
                            <span
                              className={`px-1.5 py-0.5 text-[10px] font-semibold rounded-full border capitalize ${getReminderBadge(
                                rStatus
                              )}`}
                            >
                              {rStatus}
                            </span>
                          );
                        })()}
                      </div>
                      <div className="text-[10px] text-slate-500">
                        {(() => {
                          const r24 = selectedAppt.reminders?.find((r) => r.reminder_type === "APPOINTMENT_24H");
                          if (r24?.sent_at) {
                            return `Sent: ${new Date(r24.sent_at).toLocaleTimeString("en-PK", { hour: "2-digit", minute: "2-digit" })}`;
                          }
                          if (r24?.scheduled_for) {
                            return `Due: ${new Date(r24.scheduled_for).toLocaleDateString("en-PK", { month: "short", day: "numeric" })}`;
                          }
                          return "Auto-scheduled";
                        })()}
                      </div>
                    </div>

                    {/* 2H Reminder */}
                    <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-semibold text-slate-700 text-[11px]">2h Reminder</span>
                        {(() => {
                          const r2 = selectedAppt.reminders?.find((r) => r.reminder_type === "APPOINTMENT_2H");
                          const rStatus = r2 ? r2.status : "pending";
                          return (
                            <span
                              className={`px-1.5 py-0.5 text-[10px] font-semibold rounded-full border capitalize ${getReminderBadge(
                                rStatus
                              )}`}
                            >
                              {rStatus}
                            </span>
                          );
                        })()}
                      </div>
                      <div className="text-[10px] text-slate-500">
                        {(() => {
                          const r2 = selectedAppt.reminders?.find((r) => r.reminder_type === "APPOINTMENT_2H");
                          if (r2?.sent_at) {
                            return `Sent: ${new Date(r2.sent_at).toLocaleTimeString("en-PK", { hour: "2-digit", minute: "2-digit" })}`;
                          }
                          if (r2?.scheduled_for) {
                            return `Due: ${new Date(r2.scheduled_for).toLocaleTimeString("en-PK", { hour: "2-digit", minute: "2-digit" })}`;
                          }
                          return "Auto-scheduled";
                        })()}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="pt-4 border-t border-slate-100 space-y-2">

                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Quick Actions</span>
                  {selectedAppt.status === "requested" && (
                    <button
                      onClick={() => handleStatusChange(selectedAppt.id, "confirmed")}
                      className="w-full px-3 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-sm transition"
                    >
                      Confirm Appointment
                    </button>
                  )}
                  {selectedAppt.status === "confirmed" && (
                    <>
                      <button
                        onClick={() => handleStatusChange(selectedAppt.id, "completed")}
                        className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-sm transition"
                      >
                        Mark Completed
                      </button>
                      <button
                        onClick={() => handleStatusChange(selectedAppt.id, "no_show")}
                        className="w-full px-3 py-2 bg-slate-600 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold shadow-sm transition"
                      >
                        Mark No-Show
                      </button>
                    </>
                  )}
                  {selectedAppt.status !== "cancelled" && selectedAppt.status !== "completed" && selectedAppt.status !== "no_show" && (
                    <button
                      onClick={() => handleStatusChange(selectedAppt.id, "cancelled")}
                      className="w-full px-3 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-lg text-xs font-semibold transition"
                    >
                      Cancel Appointment
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-xs text-slate-400 text-center py-12">
                Select an appointment from the list to view full details and perform actions.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

