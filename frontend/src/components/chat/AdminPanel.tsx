import { useEffect, useState } from 'react'
import {
  adminLogin,
  getAdminDashboard,
  getAdminConsultants,
  createAdminConsultant,
  updateAdminConsultant,
  deleteAdminConsultant,
  getAdminBookings,
  reassignBooking,
  cancelBooking,
  completeBooking,
  getAdminToken,
  setAdminToken,
} from '@/services/api'

type Tab = 'dashboard' | 'consultants' | 'availability' | 'bookings'

export function AdminPanel() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => Boolean(getAdminToken()))
  const [adminKey, setAdminKey] = useState('')
  const [authError, setAuthError] = useState<string | null>(null)
  const [isSubmittingAuth, setIsSubmittingAuth] = useState(false)

  const [activeTab, setActiveTab] = useState<Tab>('dashboard')
  const [dashboardData, setDashboardData] = useState<any>(null)
  const [consultants, setConsultants] = useState<any[]>([])
  const [bookings, setBookings] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Consultants editor state
  const [isAddingConsultant, setIsAddingConsultant] = useState(false)
  const [editingConsultant, setEditingConsultant] = useState<any | null>(null)
  const [consultantForm, setConsultantForm] = useState({
    id: '',
    name: '',
    email: '',
    active: true,
    calendar_id: '',
    start: '10:00',
    end: '18:00',
    days: [0, 1, 2, 3, 4], // Mon-Fri
  })

  // Leave & Vacation state
  const [selectedConsultantForLeave, setSelectedConsultantForLeave] = useState<string>('')
  const [leaveForm, setLeaveForm] = useState({
    start: '',
    end: '',
    description: '',
  })

  // Load initial data
  useEffect(() => {
    if (isAuthenticated) {
      loadAllData()
    }
  }, [isAuthenticated])

  async function loadAllData() {
    setLoading(true)
    setError(null)
    try {
      const dash = await getAdminDashboard()
      setDashboardData(dash)
      const consList = await getAdminConsultants()
      setConsultants(consList)
      const bksList = await getAdminBookings()
      setBookings(bksList)
    } catch (err) {
      console.error(err)
      setError('Failed to load admin dashboard data. Please verify your admin token or refresh.')
      // If 401, log out
      if (err instanceof Error && err.message.includes('401')) {
        handleLogout()
      }
    } finally {
      setLoading(false)
    }
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    if (!adminKey.trim()) return
    setIsSubmittingAuth(true)
    setAuthError(null)
    try {
      const res = await adminLogin(adminKey.trim())
      if (res.ok) {
        setIsAuthenticated(true)
      } else {
        setAuthError('Authentication failed.')
      }
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : 'Invalid admin key.')
    } finally {
      setIsSubmittingAuth(false)
    }
  }

  function handleLogout() {
    setAdminToken(null)
    setIsAuthenticated(false)
    setDashboardData(null)
    setConsultants([])
    setBookings([])
  }

  // Save Consultant (Add / Edit)
  async function handleSaveConsultant(e: React.FormEvent) {
    e.preventDefault()
    const payload = {
      id: consultantForm.id.trim() || `cons_${Date.now()}`,
      name: consultantForm.name.trim(),
      email: consultantForm.email.trim(),
      active: consultantForm.active,
      calendar_id: consultantForm.calendar_id.trim() || 'primary',
      working_hours: {
        start: consultantForm.start,
        end: consultantForm.end,
        days: consultantForm.days,
        timezone: 'Asia/Kolkata',
      },
      leaves: editingConsultant?.leaves ?? [],
      unavailabilities: editingConsultant?.unavailabilities ?? [],
    }

    try {
      if (editingConsultant) {
        await updateAdminConsultant(editingConsultant.id, payload)
      } else {
        await createAdminConsultant(payload)
      }
      setIsAddingConsultant(false)
      setEditingConsultant(null)
      loadAllData()
    } catch (err: any) {
      alert(err.response?.data?.detail ?? 'Failed to save consultant.')
    }
  }

  function openEditConsultant(c: any) {
    setEditingConsultant(c)
    setConsultantForm({
      id: c.id,
      name: c.name,
      email: c.email,
      active: c.active,
      calendar_id: c.calendar_id,
      start: c.working_hours.start,
      end: c.working_hours.end,
      days: c.working_hours.days,
    })
    setIsAddingConsultant(true)
  }

  function openAddConsultant() {
    setEditingConsultant(null)
    setConsultantForm({
      id: '',
      name: '',
      email: '',
      active: true,
      calendar_id: '',
      start: '10:00',
      end: '18:00',
      days: [0, 1, 2, 3, 4],
    })
    setIsAddingConsultant(true)
  }

  // Delete Consultant
  async function handleDeleteConsultant(id: string) {
    if (!confirm('Are you sure you want to delete this consultant?')) return
    try {
      await deleteAdminConsultant(id)
      loadAllData()
    } catch (err) {
      alert('Failed to delete consultant.')
    }
  }

  // Save Leave period
  async function handleAddLeave(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedConsultantForLeave || !leaveForm.start || !leaveForm.end) {
      alert('Please fill out all leave fields.')
      return
    }

    const target = consultants.find((c) => c.id === selectedConsultantForLeave)
    if (!target) return

    const newLeave = {
      start: new Date(leaveForm.start).toISOString(),
      end: new Date(leaveForm.end).toISOString(),
      description: leaveForm.description.trim() || 'Vacation',
    }

    const updatedLeaves = [...(target.leaves ?? []), newLeave]
    const payload = {
      ...target,
      leaves: updatedLeaves,
    }

    try {
      await updateAdminConsultant(target.id, payload)
      setLeaveForm({ start: '', end: '', description: '' })
      loadAllData()
      alert('Leave period added successfully.')
    } catch (err) {
      alert('Failed to add leave period.')
    }
  }

  // Remove Leave period
  async function handleRemoveLeave(cId: string, idx: number) {
    const target = consultants.find((c) => c.id === cId)
    if (!target) return
    const updatedLeaves = [...(target.leaves ?? [])]
    updatedLeaves.splice(idx, 1)

    const payload = {
      ...target,
      leaves: updatedLeaves,
    }

    try {
      await updateAdminConsultant(target.id, payload)
      loadAllData()
    } catch (err) {
      alert('Failed to remove leave period.')
    }
  }

  // Reassign booking
  async function handleReassignBooking(bId: string, newConsultantId: string) {
    setLoading(true)
    try {
      await reassignBooking(bId, newConsultantId)
      loadAllData()
      alert('Booking reassigned successfully.')
    } catch (err) {
      alert('Failed to reassign booking.')
    } finally {
      setLoading(false)
    }
  }

  // Cancel booking
  async function handleCancelBooking(bId: string) {
    if (!confirm('Are you sure you want to cancel this booking?')) return
    setLoading(true)
    try {
      await cancelBooking(bId)
      loadAllData()
      alert('Booking cancelled.')
    } catch (err) {
      alert('Failed to cancel booking.')
    } finally {
      setLoading(false)
    }
  }

  // Complete booking
  async function handleCompleteBooking(bId: string) {
    setLoading(true)
    try {
      await completeBooking(bId)
      loadAllData()
    } catch (err) {
      alert('Failed to update booking status.')
    } finally {
      setLoading(false)
    }
  }

  // Day representation
  const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

  // Render Auth Login Screen
  if (!isAuthenticated) {
    return (
      <div style={containerStyle}>
        <div style={loginCardStyle}>
          <h2 style={titleStyle}>Agicent AI Consultant</h2>
          <h3 style={{ ...subtitleStyle, marginBottom: 24 }}>Admin Authentication</h3>
          <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <label style={labelStyle}>Admin Access Key</label>
              <input
                type="password"
                placeholder="Enter admin authorization key"
                value={adminKey}
                onChange={(e) => setAdminKey(e.target.value)}
                style={inputStyle}
                disabled={isSubmittingAuth}
              />
            </div>
            {authError && <div style={errorBannerStyle}>{authError}</div>}
            <button type="submit" style={buttonStyle} disabled={isSubmittingAuth}>
              {isSubmittingAuth ? 'Verifying...' : 'Access Dashboard'}
            </button>
          </form>
        </div>
      </div>
    )
  }

  return (
    <div style={dashboardContainerStyle}>
      {/* Admin Panel Header */}
      <header style={headerStyle}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 800, color: 'var(--text)' }}>
            Admin Management Console
          </h1>
          <p style={{ fontSize: '12px', color: 'var(--text-2)', marginTop: 2 }}>
            Multi-consultant scheduling and lead routing parameters
          </p>
        </div>
        <button onClick={handleLogout} style={logoutButtonStyle}>
          Logout
        </button>
      </header>

      {/* Tabs Menu */}
      <div style={tabContainerStyle}>
        {(['dashboard', 'consultants', 'availability', 'bookings'] as Tab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => {
              setActiveTab(tab)
              setIsAddingConsultant(false)
            }}
            style={activeTab === tab ? activeTabStyle : tabStyle}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
        <button
          onClick={loadAllData}
          disabled={loading}
          style={{
            marginLeft: 'auto',
            background: 'none',
            border: '1px solid var(--border-strong)',
            color: 'var(--text)',
            borderRadius: 8,
            padding: '4px 12px',
            fontSize: '12px',
            cursor: 'pointer',
          }}
        >
          {loading ? 'Refreshing...' : 'Refresh Data'}
        </button>
      </div>

      {error && <div style={{ ...errorBannerStyle, margin: '0 0 16px 0' }}>{error}</div>}

      {/* TAB 1: DASHBOARD */}
      {activeTab === 'dashboard' && dashboardData && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Stats Cards */}
          <div style={statsGridStyle}>
            <StatCard label="Today's Discovery Calls" value={dashboardData.stats.today_bookings_count} />
            <StatCard label="Upcoming Bookings" value={dashboardData.upcoming_bookings.length} />
            <StatCard label="Active Consultants" value={dashboardData.stats.active_consultants} />
            <StatCard label="Total Consultations" value={dashboardData.stats.pending_consultations_count} />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            {/* Today's Schedule */}
            <div style={cardStyle}>
              <h3 style={sectionTitleStyle}>Today's Schedule</h3>
              {dashboardData.today_bookings.length === 0 ? (
                <div style={emptyStateStyle}>No calls scheduled for today.</div>
              ) : (
                <div style={listStyle}>
                  {dashboardData.today_bookings.map((b: any) => (
                    <div key={b.booking_id} style={listItemStyle}>
                      <div>
                        <div style={{ fontWeight: 700 }}>{b.attendee_name}</div>
                        <div style={{ fontSize: '12px', color: 'var(--text-2)' }}>{b.company ?? 'No Company'}</div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontWeight: 600, color: 'var(--accent)' }}>
                          {new Date(b.start_iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-3)' }}>
                          {consultants.find((c) => c.id === b.consultant_id)?.name ?? 'Unassigned'}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Active Team */}
            <div style={cardStyle}>
              <h3 style={sectionTitleStyle}>Team Availability Status</h3>
              <div style={listStyle}>
                {consultants.map((c: any) => (
                  <div key={c.id} style={listItemStyle}>
                    <div>
                      <div style={{ fontWeight: 700 }}>{c.name}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-2)' }}>{c.email}</div>
                    </div>
                    <div>
                      <span style={c.active ? activeBadgeStyle : inactiveBadgeStyle}>
                        {c.active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: CONSULTANTS */}
      {activeTab === 'consultants' && (
        <div>
          {isAddingConsultant ? (
            <div style={cardStyle}>
              <h3 style={sectionTitleStyle}>
                {editingConsultant ? 'Edit Consultant' : 'Add New Consultant'}
              </h3>
              <form onSubmit={handleSaveConsultant} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div style={formRowStyle}>
                  <div>
                    <label style={labelStyle}>Consultant ID</label>
                    <input
                      placeholder="e.g. jdoe"
                      value={consultantForm.id}
                      onChange={(e) => setConsultantForm({ ...consultantForm, id: e.target.value })}
                      style={inputStyle}
                      disabled={Boolean(editingConsultant)}
                      required
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Name</label>
                    <input
                      placeholder="Full Name"
                      value={consultantForm.name}
                      onChange={(e) => setConsultantForm({ ...consultantForm, name: e.target.value })}
                      style={inputStyle}
                      required
                    />
                  </div>
                </div>

                <div style={formRowStyle}>
                  <div>
                    <label style={labelStyle}>Email</label>
                    <input
                      type="email"
                      placeholder="email@company.com"
                      value={consultantForm.email}
                      onChange={(e) => setConsultantForm({ ...consultantForm, email: e.target.value })}
                      style={inputStyle}
                      required
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Google Calendar ID</label>
                    <input
                      placeholder="email address or primary"
                      value={consultantForm.calendar_id}
                      onChange={(e) => setConsultantForm({ ...consultantForm, calendar_id: e.target.value })}
                      style={inputStyle}
                      required
                    />
                  </div>
                </div>

                <div style={formRowStyle}>
                  <div>
                    <label style={labelStyle}>Shift Start Time (IST)</label>
                    <input
                      type="time"
                      value={consultantForm.start}
                      onChange={(e) => setConsultantForm({ ...consultantForm, start: e.target.value })}
                      style={inputStyle}
                      required
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Shift End Time (IST)</label>
                    <input
                      type="time"
                      value={consultantForm.end}
                      onChange={(e) => setConsultantForm({ ...consultantForm, end: e.target.value })}
                      style={inputStyle}
                      required
                    />
                  </div>
                </div>

                <div>
                  <label style={labelStyle}>Working Weekdays</label>
                  <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
                    {WEEKDAYS.map((dayName, idx) => {
                      const isSelected = consultantForm.days.includes(idx)
                      return (
                        <button
                          key={dayName}
                          type="button"
                          onClick={() => {
                            const newDays = isSelected
                              ? consultantForm.days.filter((d) => d !== idx)
                              : [...consultantForm.days, idx]
                            setConsultantForm({ ...consultantForm, days: newDays })
                          }}
                          style={isSelected ? daySelectedStyle : dayUnselectedStyle}
                        >
                          {dayName}
                        </button>
                      )
                    })}
                  </div>
                </div>

                <div>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={consultantForm.active}
                      onChange={(e) => setConsultantForm({ ...consultantForm, active: e.target.checked })}
                    />
                    <span style={{ fontWeight: 600, fontSize: '13px' }}>Status: Consultant is Active</span>
                  </label>
                </div>

                <div style={{ display: 'flex', gap: 12, marginTop: 12 }}>
                  <button type="submit" style={buttonStyle}>
                    {editingConsultant ? 'Update Consultant' : 'Add Consultant'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsAddingConsultant(false)}
                    style={secondaryButtonStyle}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          ) : (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
                <h3 style={sectionTitleStyle}>Consultants List</h3>
                <button onClick={openAddConsultant} style={buttonStyle}>
                  + Add Consultant
                </button>
              </div>

              {consultants.length === 0 ? (
                <div style={emptyStateStyle}>No consultants configured.</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  {consultants.map((c) => (
                    <div key={c.id} style={cardStyle}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontWeight: 800, fontSize: '16px' }}>{c.name}</span>
                            <span style={c.active ? activeBadgeStyle : inactiveBadgeStyle}>
                              {c.active ? 'Active' : 'Inactive'}
                            </span>
                          </div>
                          <div style={{ fontSize: '13px', color: 'var(--text-2)', marginTop: 4 }}>
                            Email: {c.email} | Calendar: {c.calendar_id}
                          </div>
                          <div style={{ fontSize: '12px', color: 'var(--text-3)', marginTop: 4 }}>
                            Hours: {c.working_hours.start} - {c.working_hours.end} IST | Days:{' '}
                            {c.working_hours.days.map((d: number) => WEEKDAYS[d]).join(', ')}
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: 8 }}>
                          <button onClick={() => openEditConsultant(c)} style={editButtonStyle}>
                            Edit
                          </button>
                          <button
                            onClick={() => handleDeleteConsultant(c.id)}
                            style={deleteButtonStyle}
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: AVAILABILITY (LEAVES / VACATIONS) */}
      {activeTab === 'availability' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1.8fr', gap: 20 }}>
          {/* Add Leave Form */}
          <div style={cardStyle}>
            <h3 style={sectionTitleStyle}>Add Leave / Vacation Period</h3>
            <form onSubmit={handleAddLeave} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={labelStyle}>Select Consultant</label>
                <select
                  value={selectedConsultantForLeave}
                  onChange={(e) => setSelectedConsultantForLeave(e.target.value)}
                  style={selectStyle}
                  required
                >
                  <option value="">-- Choose Consultant --</option>
                  {consultants.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.id})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={labelStyle}>Start Date &amp; Time (Local)</label>
                <input
                  type="datetime-local"
                  value={leaveForm.start}
                  onChange={(e) => setLeaveForm({ ...leaveForm, start: e.target.value })}
                  style={inputStyle}
                  required
                />
              </div>

              <div>
                <label style={labelStyle}>End Date &amp; Time (Local)</label>
                <input
                  type="datetime-local"
                  value={leaveForm.end}
                  onChange={(e) => setLeaveForm({ ...leaveForm, end: e.target.value })}
                  style={inputStyle}
                  required
                />
              </div>

              <div>
                <label style={labelStyle}>Description / Reason</label>
                <input
                  placeholder="e.g. Annual Vacation, Doctor visit"
                  value={leaveForm.description}
                  onChange={(e) => setLeaveForm({ ...leaveForm, description: e.target.value })}
                  style={inputStyle}
                />
              </div>

              <button type="submit" style={{ ...buttonStyle, marginTop: 8 }}>
                Add Leave Block
              </button>
            </form>
          </div>

          {/* Current Leaves List */}
          <div style={cardStyle}>
            <h3 style={sectionTitleStyle}>Scheduled Leave / Vacation Periods</h3>
            <div style={{ maxHeight: '420px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
              {consultants.every((c) => !c.leaves || c.leaves.length === 0) ? (
                <div style={emptyStateStyle}>No leaves scheduled.</div>
              ) : (
                consultants.map((c) => {
                  if (!c.leaves || c.leaves.length === 0) return null
                  return (
                    <div key={c.id} style={{ borderBottom: '1px solid var(--border)', paddingBottom: 10 }}>
                      <div style={{ fontWeight: 700, fontSize: '14px', marginBottom: 6 }}>{c.name}</div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {c.leaves.map((leave: any, idx: number) => (
                          <div
                            key={idx}
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              background: 'var(--bg-2)',
                              padding: '6px 10px',
                              borderRadius: 8,
                              fontSize: '12px',
                              alignItems: 'center',
                            }}
                          >
                            <div>
                              <div style={{ fontWeight: 600 }}>{leave.description}</div>
                              <div style={{ color: 'var(--text-3)', marginTop: 2 }}>
                                {new Date(leave.start).toLocaleString()} - {new Date(leave.end).toLocaleString()}
                              </div>
                            </div>
                            <button
                              onClick={() => handleRemoveLeave(c.id, idx)}
                              style={{
                                border: 'none',
                                background: 'none',
                                color: 'var(--accent)',
                                fontSize: '11px',
                                cursor: 'pointer',
                                fontWeight: 700,
                              }}
                            >
                              Remove
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: BOOKINGS */}
      {activeTab === 'bookings' && (
        <div style={cardStyle}>
          <h3 style={sectionTitleStyle}>Discovery Call Bookings</h3>
          {bookings.length === 0 ? (
            <div style={emptyStateStyle}>No bookings found in the database.</div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={tableStyle}>
                <thead>
                  <tr>
                    <th style={thStyle}>Client</th>
                    <th style={thStyle}>Date &amp; Time (Local)</th>
                    <th style={thStyle}>Topic / Context</th>
                    <th style={thStyle}>Assigned Consultant</th>
                    <th style={thStyle}>Status</th>
                    <th style={thStyle}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {bookings.map((b) => (
                    <tr key={b.booking_id} style={trStyle}>
                      <td style={tdStyle}>
                        <div style={{ fontWeight: 700 }}>{b.attendee_name}</div>
                        <div style={{ fontSize: '11px', color: 'var(--text-3)' }}>{b.attendee_email}</div>
                        {b.company && (
                          <div style={{ fontSize: '11px', color: 'var(--text-2)', marginTop: 2 }}>
                            💼 {b.company}
                          </div>
                        )}
                      </td>
                      <td style={tdStyle}>
                        <div style={{ fontWeight: 600 }}>
                          {new Date(b.start_iso).toLocaleDateString([], {
                            month: 'short',
                            day: 'numeric',
                            year: 'numeric',
                          })}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-3)' }}>
                          {new Date(b.start_iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                      </td>
                      <td style={{ ...tdStyle, maxWidth: '200px', fontSize: '12px' }}>
                        {b.topic_summary ? (
                          <span title={b.topic_summary}>
                            {b.topic_summary.length > 60 ? `${b.topic_summary.slice(0, 60)}...` : b.topic_summary}
                          </span>
                        ) : (
                          <span style={{ color: 'var(--text-3)', fontStyle: 'italic' }}>None provided</span>
                        )}
                      </td>
                      <td style={tdStyle}>
                        <select
                          value={b.consultant_id}
                          onChange={(e) => handleReassignBooking(b.booking_id, e.target.value)}
                          disabled={b.status === 'cancelled'}
                          style={reassignSelectStyle}
                        >
                          {/* Fallback for legacy consultant IDs not in current list */}
                          {!consultants.some((c) => c.id === b.consultant_id) && (
                            <option value={b.consultant_id} disabled>
                              {b.consultant_id} (legacy)
                            </option>
                          )}
                          {consultants.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td style={tdStyle}>
                        <span style={getStatusBadgeStyle(b.status)}>{b.status.toUpperCase()}</span>
                      </td>
                      <td style={tdStyle}>
                        <div style={{ display: 'flex', gap: 6 }}>
                          {b.status === 'scheduled' && (
                            <>
                              <button
                                onClick={() => handleCompleteBooking(b.booking_id)}
                                style={actionCompleteStyle}
                              >
                                Complete
                              </button>
                              <button
                                onClick={() => handleCancelBooking(b.booking_id)}
                                style={actionCancelStyle}
                              >
                                Cancel
                              </button>
                            </>
                          )}
                          {/* Open Calendar: prefer attendee_link (Discovery Calls calendar) */}
                          {(b.attendee_link || b.html_link) && (
                            <a
                              href={b.attendee_link || b.html_link}
                              target="_blank"
                              rel="noreferrer"
                              style={actionLinkStyle}
                            >
                              Open Calendar
                            </a>
                          )}
                          {/* Meet link for quick join from admin */}
                          {(b as any).meet_link && (
                            <a
                              href={(b as any).meet_link}
                              target="_blank"
                              rel="noreferrer"
                              style={{ ...actionLinkStyle, color: 'var(--accent)', borderColor: 'var(--accent)' }}
                            >
                              Join Meet
                            </a>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Small Components ──────────────────────────────────────────────────────

function StatCard({ label, value }: { label: string; value: any }) {
  return (
    <div style={statCardStyle}>
      <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)' }}>{label}</div>
      <div style={{ fontSize: '28px', fontWeight: 800, color: 'var(--text)', marginTop: 8 }}>{value}</div>
    </div>
  )
}

// ── Inline CSS Styles ──────────────────────────────────────────────────────

const containerStyle: React.CSSProperties = {
  minHeight: '80vh',
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  padding: '24px',
  background: 'var(--bg-2, #fafafa)',
}

const loginCardStyle: React.CSSProperties = {
  width: '100%',
  maxWidth: '420px',
  padding: '32px',
  background: 'var(--bg, #ffffff)',
  borderRadius: '16px',
  border: '1px solid var(--border-strong)',
  boxShadow: 'var(--shadow-lg)',
}

const titleStyle: React.CSSProperties = {
  fontSize: '24px',
  fontWeight: 800,
  textAlign: 'center',
  color: 'var(--accent, #e23e30)',
  marginBottom: '6px',
  letterSpacing: '-0.02em',
}

const subtitleStyle: React.CSSProperties = {
  fontSize: '14px',
  fontWeight: 600,
  textAlign: 'center',
  color: 'var(--text-2)',
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: '12px',
  fontWeight: 700,
  color: 'var(--text-2)',
  marginBottom: '6px',
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '10px 12px',
  borderRadius: '8px',
  border: '1px solid var(--border-strong)',
  background: 'var(--bg-2)',
  color: 'var(--text)',
  fontSize: '14px',
  outline: 'none',
  boxSizing: 'border-box',
  fontFamily: 'var(--font)',
}

const selectStyle: React.CSSProperties = {
  width: '100%',
  padding: '10px 12px',
  borderRadius: '8px',
  border: '1px solid var(--border-strong)',
  background: 'var(--bg-2)',
  color: 'var(--text)',
  fontSize: '14px',
  outline: 'none',
  boxSizing: 'border-box',
}

const buttonStyle: React.CSSProperties = {
  width: '100%',
  padding: '12px',
  borderRadius: '8px',
  border: 'none',
  background: 'var(--agicent-gradient-trigger, var(--accent, #e23e30))',
  color: 'white',
  fontWeight: 700,
  fontSize: '14px',
  cursor: 'pointer',
  transition: 'opacity 0.15s ease',
}

const secondaryButtonStyle: React.CSSProperties = {
  width: '100%',
  padding: '12px',
  borderRadius: '8px',
  border: '1px solid var(--border-strong)',
  background: 'var(--bg)',
  color: 'var(--text)',
  fontWeight: 600,
  fontSize: '14px',
  cursor: 'pointer',
}

const errorBannerStyle: React.CSSProperties = {
  padding: '10px 12px',
  borderRadius: '8px',
  background: 'rgba(239, 68, 68, 0.1)',
  border: '1px solid rgba(239, 68, 68, 0.2)',
  color: '#dc2626',
  fontSize: '12px',
  fontWeight: 500,
}

// Dashboard Console Styles
const dashboardContainerStyle: React.CSSProperties = {
  padding: '24px',
  maxWidth: '1200px',
  margin: '0 auto',
}

const headerStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  borderBottom: '1px solid var(--border-strong)',
  paddingBottom: '16px',
  marginBottom: '20px',
}

const logoutButtonStyle: React.CSSProperties = {
  background: 'none',
  border: '1px solid var(--accent)',
  color: 'var(--accent)',
  borderRadius: '8px',
  padding: '6px 14px',
  fontWeight: 700,
  fontSize: '13px',
  cursor: 'pointer',
}

const tabContainerStyle: React.CSSProperties = {
  display: 'flex',
  gap: '8px',
  borderBottom: '1px solid var(--border)',
  marginBottom: '24px',
  paddingBottom: '8px',
  alignItems: 'center',
}

const tabStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  padding: '8px 16px',
  fontSize: '14px',
  fontWeight: 600,
  color: 'var(--text-2)',
  cursor: 'pointer',
  borderRadius: '8px',
}

const activeTabStyle: React.CSSProperties = {
  ...tabStyle,
  background: 'rgba(226, 62, 48, 0.08)',
  color: 'var(--accent)',
  fontWeight: 700,
}

const statsGridStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
  gap: '16px',
}

const statCardStyle: React.CSSProperties = {
  background: 'var(--bg)',
  border: '1px solid var(--border-strong)',
  borderRadius: '12px',
  padding: '20px',
  boxShadow: 'var(--shadow-sm)',
}

const cardStyle: React.CSSProperties = {
  background: 'var(--bg)',
  border: '1px solid var(--border-strong)',
  borderRadius: '14px',
  padding: '20px',
  boxShadow: 'var(--shadow-sm)',
}

const sectionTitleStyle: React.CSSProperties = {
  fontSize: '16px',
  fontWeight: 800,
  color: 'var(--text)',
  marginBottom: '16px',
}

const emptyStateStyle: React.CSSProperties = {
  textAlign: 'center',
  padding: '32px 16px',
  color: 'var(--text-3)',
  fontSize: '14px',
  fontStyle: 'italic',
}

const listStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: '12px',
}

const listItemStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  paddingBottom: '10px',
  borderBottom: '1px solid var(--border)',
}

const activeBadgeStyle: React.CSSProperties = {
  background: 'rgba(34, 197, 94, 0.1)',
  color: '#16a34a',
  borderRadius: '6px',
  padding: '2px 8px',
  fontSize: '11px',
  fontWeight: 700,
}

const inactiveBadgeStyle: React.CSSProperties = {
  background: 'rgba(107, 114, 128, 0.1)',
  color: '#4b5563',
  borderRadius: '6px',
  padding: '2px 8px',
  fontSize: '11px',
  fontWeight: 700,
}

const editButtonStyle: React.CSSProperties = {
  background: 'none',
  border: '1px solid var(--border-strong)',
  color: 'var(--text)',
  borderRadius: '6px',
  padding: '4px 10px',
  fontSize: '12px',
  fontWeight: 600,
  cursor: 'pointer',
}

const deleteButtonStyle: React.CSSProperties = {
  background: 'none',
  border: '1px solid var(--accent)',
  color: 'var(--accent)',
  borderRadius: '6px',
  padding: '4px 10px',
  fontSize: '12px',
  fontWeight: 600,
  cursor: 'pointer',
}

const formRowStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: '1fr 1fr',
  gap: '12px',
}

const dayUnselectedStyle: React.CSSProperties = {
  background: 'var(--bg-2)',
  border: '1px solid var(--border-strong)',
  color: 'var(--text-2)',
  borderRadius: '6px',
  padding: '6px 12px',
  fontSize: '12px',
  cursor: 'pointer',
  fontWeight: 600,
}

const daySelectedStyle: React.CSSProperties = {
  ...dayUnselectedStyle,
  background: 'var(--accent)',
  color: 'white',
  border: 'none',
}

// Bookings Table Styles
const tableStyle: React.CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse',
  textAlign: 'left',
}

const thStyle: React.CSSProperties = {
  padding: '12px 8px',
  borderBottom: '2px solid var(--border-strong)',
  fontSize: '12px',
  fontWeight: 700,
  color: 'var(--text-2)',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
}

const trStyle: React.CSSProperties = {
  borderBottom: '1px solid var(--border)',
}

const tdStyle: React.CSSProperties = {
  padding: '12px 8px',
  fontSize: '13px',
  verticalAlign: 'middle',
}

const reassignSelectStyle: React.CSSProperties = {
  padding: '6px 8px',
  borderRadius: '6px',
  border: '1px solid var(--border-strong)',
  background: 'var(--bg-2)',
  color: 'var(--text)',
  fontSize: '12px',
  outline: 'none',
}

const actionCompleteStyle: React.CSSProperties = {
  background: '#16a34a',
  color: 'white',
  border: 'none',
  borderRadius: '6px',
  padding: '4px 8px',
  fontSize: '11px',
  fontWeight: 700,
  cursor: 'pointer',
}

const actionCancelStyle: React.CSSProperties = {
  background: 'var(--accent)',
  color: 'white',
  border: 'none',
  borderRadius: '6px',
  padding: '4px 8px',
  fontSize: '11px',
  fontWeight: 700,
  cursor: 'pointer',
}

const actionLinkStyle: React.CSSProperties = {
  border: '1px solid var(--border-strong)',
  color: 'var(--text)',
  textDecoration: 'none',
  borderRadius: '6px',
  padding: '4px 8px',
  fontSize: '11px',
  fontWeight: 600,
  display: 'inline-block',
}

function getStatusBadgeStyle(status: string): React.CSSProperties {
  switch (status) {
    case 'scheduled':
      return {
        background: 'rgba(30, 64, 175, 0.1)',
        color: '#1e40af',
        borderRadius: '6px',
        padding: '2px 6px',
        fontSize: '11px',
        fontWeight: 700,
      }
    case 'completed':
      return {
        background: 'rgba(22, 163, 74, 0.1)',
        color: '#16a34a',
        borderRadius: '6px',
        padding: '2px 6px',
        fontSize: '11px',
        fontWeight: 700,
      }
    case 'cancelled':
      return {
        background: 'rgba(220, 38, 38, 0.1)',
        color: '#dc2626',
        borderRadius: '6px',
        padding: '2px 6px',
        fontSize: '11px',
        fontWeight: 700,
      }
    default:
      return {}
  }
}
