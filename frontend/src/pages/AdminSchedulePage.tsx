import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { AdminLayout } from '../components/AdminLayout'
import { useAuth } from '../auth/AuthContext'
import { fetchAdminStaff } from '../api/staff'
import {
  createBlockedPeriod,
  deleteBlockedPeriod,
  fetchBlockedPeriods,
  fetchWorkingHours,
  updateBlockedPeriod,
} from '../api/schedule'
import { ApiError } from '../api/errors'
import { isUnauthorizedError } from '../api/auth'
import type { StaffListItem } from '../types/staff'
import type {
  BlockType,
  BlockedPeriodItem,
  WorkingHoursItem,
} from '../types/schedule'

const DAY_NAMES = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
] as const

const BLOCK_TYPE_OPTIONS: { value: '' | BlockType; label: string }[] = [
  { value: '', label: 'All types' },
  { value: 'manual', label: 'Manual' },
  { value: 'holiday', label: 'Holiday' },
  { value: 'time_off', label: 'Time off' },
]

const WH_SCOPE_SALON = ''

function canManageSchedule(role: string | undefined): boolean {
  return role === 'owner' || role === 'admin'
}

function formatTimeOfDay(timeStr: string): string {
  const parts = timeStr.split(':')
  const hours = Number(parts[0])
  const minutes = Number(parts[1] ?? 0)
  const date = new Date()
  date.setHours(hours, minutes, 0, 0)
  return date.toLocaleTimeString(undefined, { timeStyle: 'short' })
}

function formatDateOnly(isoDate: string): string {
  const [y, m, d] = isoDate.split('-').map(Number)
  const date = new Date(y, m - 1, d)
  return date.toLocaleDateString(undefined, { dateStyle: 'medium' })
}

function formatDateTime(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

function datetimeLocalToIso(value: string): string {
  return new Date(value).toISOString()
}

function isoToDatetimeLocal(iso: string): string {
  const date = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function staffLabel(
  staffId: string | null,
  staffById: Map<string, StaffListItem>,
): string {
  if (staffId === null) {
    return 'Salon (all staff)'
  }
  return staffById.get(staffId)?.display_name ?? staffId
}

type BlockedPeriodFormState = {
  staffId: string
  startsAtLocal: string
  endsAtLocal: string
  reason: string
  blockType: BlockType
}

const emptyBlockedForm = (): BlockedPeriodFormState => ({
  staffId: '',
  startsAtLocal: '',
  endsAtLocal: '',
  reason: '',
  blockType: 'manual',
})

function blockedFormFromRow(row: BlockedPeriodItem): BlockedPeriodFormState {
  return {
    staffId: row.staff_id ?? '',
    startsAtLocal: isoToDatetimeLocal(row.starts_at),
    endsAtLocal: isoToDatetimeLocal(row.ends_at),
    reason: row.reason ?? '',
    blockType: (row.block_type as BlockType) || 'manual',
  }
}

function formToCreateBody(form: BlockedPeriodFormState) {
  return {
    staff_id: form.staffId === '' ? null : form.staffId,
    starts_at: datetimeLocalToIso(form.startsAtLocal),
    ends_at: datetimeLocalToIso(form.endsAtLocal),
    reason: form.reason.trim() === '' ? null : form.reason.trim(),
    block_type: form.blockType,
  }
}

function formToUpdateBody(form: BlockedPeriodFormState) {
  return {
    staff_id: form.staffId === '' ? null : form.staffId,
    starts_at: datetimeLocalToIso(form.startsAtLocal),
    ends_at: datetimeLocalToIso(form.endsAtLocal),
    reason: form.reason.trim() === '' ? null : form.reason.trim(),
    block_type: form.blockType,
  }
}

export function AdminSchedulePage() {
  const { session, clearAuthAndRedirect } = useAuth()
  const manage = canManageSchedule(session?.salon.role)

  const [staffList, setStaffList] = useState<StaffListItem[]>([])
  const [staffLoading, setStaffLoading] = useState(true)

  const [whScopeStaffId, setWhScopeStaffId] = useState(WH_SCOPE_SALON)
  const [workingHours, setWorkingHours] = useState<WorkingHoursItem[]>([])
  const [whLoading, setWhLoading] = useState(true)
  const [whError, setWhError] = useState<string | null>(null)

  const [bpFilterStaffId, setBpFilterStaffId] = useState('')
  const [bpFilterStartsFrom, setBpFilterStartsFrom] = useState('')
  const [bpFilterEndsTo, setBpFilterEndsTo] = useState('')
  const [bpFilterBlockType, setBpFilterBlockType] = useState<'' | BlockType>('')
  const [appliedBpFilters, setAppliedBpFilters] = useState<{
    staff_id?: string
    starts_from?: string
    ends_to?: string
    block_type?: BlockType
  }>({})

  const [blockedPeriods, setBlockedPeriods] = useState<BlockedPeriodItem[]>([])
  const [bpLoading, setBpLoading] = useState(true)
  const [bpError, setBpError] = useState<string | null>(null)
  const [bpActionError, setBpActionError] = useState<string | null>(null)
  const [bpSaving, setBpSaving] = useState(false)

  const [createForm, setCreateForm] = useState<BlockedPeriodFormState>(emptyBlockedForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<BlockedPeriodFormState>(emptyBlockedForm)

  const staffById = useMemo(() => {
    const map = new Map<string, StaffListItem>()
    for (const row of staffList) {
      map.set(row.id, row)
    }
    return map
  }, [staffList])

  const loadStaff = useCallback(async () => {
    if (!session) {
      return
    }
    setStaffLoading(true)
    try {
      const rows = await fetchAdminStaff(session.token, session.salon.salon_id, {
        active_only: true,
      })
      setStaffList(rows)
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      setStaffList([])
    } finally {
      setStaffLoading(false)
    }
  }, [session, clearAuthAndRedirect])

  const loadWorkingHours = useCallback(async () => {
    if (!session) {
      return
    }
    setWhLoading(true)
    setWhError(null)
    try {
      const params =
        whScopeStaffId === WH_SCOPE_SALON
          ? {}
          : { staff_id: whScopeStaffId }
      const rows = await fetchWorkingHours(session.token, session.salon.salon_id, params)
      const scoped =
        whScopeStaffId === WH_SCOPE_SALON
          ? rows.filter((row) => row.staff_id === null)
          : rows
      setWorkingHours(scoped)
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      if (err instanceof ApiError) {
        setWhError(err.message)
      } else {
        setWhError('Could not load working hours.')
      }
      setWorkingHours([])
    } finally {
      setWhLoading(false)
    }
  }, [session, whScopeStaffId, clearAuthAndRedirect])

  const loadBlockedPeriods = useCallback(async () => {
    if (!session) {
      return
    }
    setBpLoading(true)
    setBpError(null)
    try {
      const rows = await fetchBlockedPeriods(
        session.token,
        session.salon.salon_id,
        appliedBpFilters,
      )
      setBlockedPeriods(rows)
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      if (err instanceof ApiError) {
        setBpError(err.message)
      } else {
        setBpError('Could not load blocked periods.')
      }
      setBlockedPeriods([])
    } finally {
      setBpLoading(false)
    }
  }, [session, appliedBpFilters, clearAuthAndRedirect])

  useEffect(() => {
    void loadStaff()
  }, [loadStaff])

  useEffect(() => {
    void loadWorkingHours()
  }, [loadWorkingHours])

  useEffect(() => {
    void loadBlockedPeriods()
  }, [loadBlockedPeriods])

  const hoursByDay = useMemo(() => {
    const map = new Map<number, WorkingHoursItem[]>()
    for (const row of workingHours) {
      const list = map.get(row.day_of_week) ?? []
      list.push(row)
      map.set(row.day_of_week, list)
    }
    return map
  }, [workingHours])

  const closedDayNames = useMemo(() => {
    const closed: string[] = []
    for (let day = 0; day <= 6; day += 1) {
      if (!hoursByDay.has(day)) {
        closed.push(DAY_NAMES[day])
      }
    }
    return closed
  }, [hoursByDay])

  function handleBpFiltersSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const next: typeof appliedBpFilters = {}
    if (bpFilterStaffId !== '') {
      next.staff_id = bpFilterStaffId
    }
    if (bpFilterStartsFrom !== '') {
      next.starts_from = datetimeLocalToIso(bpFilterStartsFrom)
    }
    if (bpFilterEndsTo !== '') {
      next.ends_to = datetimeLocalToIso(bpFilterEndsTo)
    }
    if (bpFilterBlockType !== '') {
      next.block_type = bpFilterBlockType
    }
    setAppliedBpFilters(next)
  }

  async function handleCreateBlocked(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!session || !manage) {
      return
    }
    setBpSaving(true)
    setBpActionError(null)
    try {
      await createBlockedPeriod(
        session.token,
        session.salon.salon_id,
        formToCreateBody(createForm),
      )
      setCreateForm(emptyBlockedForm())
      await loadBlockedPeriods()
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      if (err instanceof ApiError) {
        setBpActionError(err.message)
      } else {
        setBpActionError('Could not create blocked period.')
      }
    } finally {
      setBpSaving(false)
    }
  }

  function startEdit(row: BlockedPeriodItem) {
    setEditingId(row.id)
    setEditForm(blockedFormFromRow(row))
    setBpActionError(null)
  }

  function cancelEdit() {
    setEditingId(null)
    setEditForm(emptyBlockedForm())
  }

  async function handleUpdateBlocked(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!session || !manage || editingId === null) {
      return
    }
    setBpSaving(true)
    setBpActionError(null)
    try {
      await updateBlockedPeriod(
        session.token,
        session.salon.salon_id,
        editingId,
        formToUpdateBody(editForm),
      )
      cancelEdit()
      await loadBlockedPeriods()
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      if (err instanceof ApiError) {
        setBpActionError(err.message)
      } else {
        setBpActionError('Could not update blocked period.')
      }
    } finally {
      setBpSaving(false)
    }
  }

  async function handleDeleteBlocked(row: BlockedPeriodItem) {
    if (!session || !manage) {
      return
    }
    const ok = window.confirm('Delete this blocked period?')
    if (!ok) {
      return
    }
    setBpSaving(true)
    setBpActionError(null)
    try {
      await deleteBlockedPeriod(session.token, session.salon.salon_id, row.id)
      if (editingId === row.id) {
        cancelEdit()
      }
      await loadBlockedPeriods()
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearAuthAndRedirect()
        return
      }
      if (err instanceof ApiError) {
        setBpActionError(err.message)
      } else {
        setBpActionError('Could not delete blocked period.')
      }
    } finally {
      setBpSaving(false)
    }
  }

  return (
    <AdminLayout>
      <div className="admin-schedule">
        <header className="admin-schedule__header">
          <h1 className="admin-schedule__title">Schedule</h1>
          <p className="admin-schedule__lead">
            Working hours are read-only. Blocked periods can be managed by owners and admins.
          </p>
        </header>

        <section className="admin-schedule__section" aria-labelledby="admin-schedule-wh-heading">
          <h2 id="admin-schedule-wh-heading" className="admin-schedule__section-title">
            Working hours
          </h2>

          <div className="admin-schedule__filters">
            <label className="admin-schedule__filter">
              <span>Scope</span>
              <select
                value={whScopeStaffId}
                onChange={(event) => setWhScopeStaffId(event.target.value)}
                disabled={staffLoading}
              >
                <option value={WH_SCOPE_SALON}>Salon default</option>
                {staffList.map((staff) => (
                  <option key={staff.id} value={staff.id}>
                    {staff.display_name}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {whLoading ? (
            <p className="admin-schedule__state" role="status">
              Loading working hours…
            </p>
          ) : null}

          {!whLoading && whError ? (
            <p className="admin-schedule__state admin-schedule__state--error" role="alert">
              {whError}
            </p>
          ) : null}

          {!whLoading && !whError ? (
            <>
              <div className="admin-schedule__weekly">
                <ul className="admin-schedule__weekly-list">
                  {DAY_NAMES.map((name, index) => {
                    const dayRows = hoursByDay.get(index) ?? []
                    return (
                      <li key={name} className="admin-schedule__weekly-day">
                        <span className="admin-schedule__weekly-day-name">{name}</span>
                        {dayRows.length === 0 ? (
                          <span className="admin-schedule__weekly-closed">Closed</span>
                        ) : (
                          <ul className="admin-schedule__weekly-slots">
                            {dayRows.map((row) => (
                              <li key={row.id}>
                                {formatTimeOfDay(row.start_time)} – {formatTimeOfDay(row.end_time)}
                              </li>
                            ))}
                          </ul>
                        )}
                      </li>
                    )
                  })}
                </ul>
              </div>

              {closedDayNames.length > 0 ? (
                <p className="admin-schedule__closed-summary">
                  Closed days: {closedDayNames.join(', ')}
                </p>
              ) : (
                <p className="admin-schedule__closed-summary">No closed days in this scope.</p>
              )}

              {workingHours.length > 0 ? (
                <div className="admin-schedule__table-wrap">
                  <table className="admin-schedule__table">
                    <thead>
                      <tr>
                        <th scope="col">Day</th>
                        <th scope="col">Start</th>
                        <th scope="col">End</th>
                        <th scope="col">Effective from</th>
                        <th scope="col">Effective to</th>
                      </tr>
                    </thead>
                    <tbody>
                      {workingHours.map((row) => (
                        <tr key={row.id}>
                          <td>{DAY_NAMES[row.day_of_week]}</td>
                          <td>{formatTimeOfDay(row.start_time)}</td>
                          <td>{formatTimeOfDay(row.end_time)}</td>
                          <td>{row.effective_from ? formatDateOnly(row.effective_from) : '—'}</td>
                          <td>{row.effective_to ? formatDateOnly(row.effective_to) : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="admin-schedule__state">No working hours defined for this scope.</p>
              )}
            </>
          ) : null}
        </section>

        <section className="admin-schedule__section" aria-labelledby="admin-schedule-bp-heading">
          <h2 id="admin-schedule-bp-heading" className="admin-schedule__section-title">
            Blocked periods
          </h2>

          <form className="admin-schedule__filters" onSubmit={handleBpFiltersSubmit}>
            <label className="admin-schedule__filter">
              <span>Staff</span>
              <select
                value={bpFilterStaffId}
                onChange={(event) => setBpFilterStaffId(event.target.value)}
              >
                <option value="">All</option>
                {staffList.map((staff) => (
                  <option key={staff.id} value={staff.id}>
                    {staff.display_name}
                  </option>
                ))}
              </select>
            </label>
            <label className="admin-schedule__filter">
              <span>Starts from</span>
              <input
                type="datetime-local"
                value={bpFilterStartsFrom}
                onChange={(event) => setBpFilterStartsFrom(event.target.value)}
              />
            </label>
            <label className="admin-schedule__filter">
              <span>Ends to</span>
              <input
                type="datetime-local"
                value={bpFilterEndsTo}
                onChange={(event) => setBpFilterEndsTo(event.target.value)}
              />
            </label>
            <label className="admin-schedule__filter">
              <span>Block type</span>
              <select
                value={bpFilterBlockType}
                onChange={(event) =>
                  setBpFilterBlockType(event.target.value as '' | BlockType)
                }
              >
                {BLOCK_TYPE_OPTIONS.map((option) => (
                  <option key={option.label} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" className="btn btn--secondary btn--compact">
              Apply
            </button>
          </form>

          {manage ? (
            <form
              className="admin-schedule__form admin-schedule__form--create"
              onSubmit={handleCreateBlocked}
            >
              <h3 className="admin-schedule__form-title">Add blocked period</h3>
              <div className="admin-schedule__form-grid">
                <label className="admin-schedule__filter">
                  <span>Staff</span>
                  <select
                    value={createForm.staffId}
                    onChange={(event) =>
                      setCreateForm((prev) => ({ ...prev, staffId: event.target.value }))
                    }
                  >
                    <option value="">Salon (all staff)</option>
                    {staffList.map((staff) => (
                      <option key={staff.id} value={staff.id}>
                        {staff.display_name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="admin-schedule__filter">
                  <span>Starts at</span>
                  <input
                    type="datetime-local"
                    required
                    value={createForm.startsAtLocal}
                    onChange={(event) =>
                      setCreateForm((prev) => ({ ...prev, startsAtLocal: event.target.value }))
                    }
                  />
                </label>
                <label className="admin-schedule__filter">
                  <span>Ends at</span>
                  <input
                    type="datetime-local"
                    required
                    value={createForm.endsAtLocal}
                    onChange={(event) =>
                      setCreateForm((prev) => ({ ...prev, endsAtLocal: event.target.value }))
                    }
                  />
                </label>
                <label className="admin-schedule__filter">
                  <span>Block type</span>
                  <select
                    value={createForm.blockType}
                    onChange={(event) =>
                      setCreateForm((prev) => ({
                        ...prev,
                        blockType: event.target.value as BlockType,
                      }))
                    }
                  >
                    <option value="manual">Manual</option>
                    <option value="holiday">Holiday</option>
                    <option value="time_off">Time off</option>
                  </select>
                </label>
                <label className="admin-schedule__filter admin-schedule__filter--wide">
                  <span>Reason</span>
                  <input
                    type="text"
                    maxLength={255}
                    value={createForm.reason}
                    onChange={(event) =>
                      setCreateForm((prev) => ({ ...prev, reason: event.target.value }))
                    }
                    placeholder="Optional"
                  />
                </label>
              </div>
              <button
                type="submit"
                className="btn btn--primary btn--compact"
                disabled={bpSaving}
              >
                Create
              </button>
            </form>
          ) : null}

          {bpActionError ? (
            <p className="admin-schedule__state admin-schedule__state--error" role="alert">
              {bpActionError}
            </p>
          ) : null}

          {editingId !== null && manage ? (
            <form
              className="admin-schedule__form admin-schedule__form--edit"
              onSubmit={handleUpdateBlocked}
            >
              <h3 className="admin-schedule__form-title">Edit blocked period</h3>
              <div className="admin-schedule__form-grid">
                <label className="admin-schedule__filter">
                  <span>Staff</span>
                  <select
                    value={editForm.staffId}
                    onChange={(event) =>
                      setEditForm((prev) => ({ ...prev, staffId: event.target.value }))
                    }
                  >
                    <option value="">Salon (all staff)</option>
                    {staffList.map((staff) => (
                      <option key={staff.id} value={staff.id}>
                        {staff.display_name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="admin-schedule__filter">
                  <span>Starts at</span>
                  <input
                    type="datetime-local"
                    required
                    value={editForm.startsAtLocal}
                    onChange={(event) =>
                      setEditForm((prev) => ({ ...prev, startsAtLocal: event.target.value }))
                    }
                  />
                </label>
                <label className="admin-schedule__filter">
                  <span>Ends at</span>
                  <input
                    type="datetime-local"
                    required
                    value={editForm.endsAtLocal}
                    onChange={(event) =>
                      setEditForm((prev) => ({ ...prev, endsAtLocal: event.target.value }))
                    }
                  />
                </label>
                <label className="admin-schedule__filter">
                  <span>Block type</span>
                  <select
                    value={editForm.blockType}
                    onChange={(event) =>
                      setEditForm((prev) => ({
                        ...prev,
                        blockType: event.target.value as BlockType,
                      }))
                    }
                  >
                    <option value="manual">Manual</option>
                    <option value="holiday">Holiday</option>
                    <option value="time_off">Time off</option>
                  </select>
                </label>
                <label className="admin-schedule__filter admin-schedule__filter--wide">
                  <span>Reason</span>
                  <input
                    type="text"
                    maxLength={255}
                    value={editForm.reason}
                    onChange={(event) =>
                      setEditForm((prev) => ({ ...prev, reason: event.target.value }))
                    }
                    placeholder="Optional"
                  />
                </label>
              </div>
              <div className="admin-schedule__form-actions">
                <button
                  type="submit"
                  className="btn btn--primary btn--compact"
                  disabled={bpSaving}
                >
                  Save
                </button>
                <button
                  type="button"
                  className="btn btn--secondary btn--compact"
                  onClick={cancelEdit}
                  disabled={bpSaving}
                >
                  Cancel
                </button>
              </div>
            </form>
          ) : null}

          {bpLoading ? (
            <p className="admin-schedule__state" role="status">
              Loading blocked periods…
            </p>
          ) : null}

          {!bpLoading && bpError ? (
            <p className="admin-schedule__state admin-schedule__state--error" role="alert">
              {bpError}
            </p>
          ) : null}

          {!bpLoading && !bpError && blockedPeriods.length === 0 ? (
            <p className="admin-schedule__state">No blocked periods match your filters.</p>
          ) : null}

          {!bpLoading && !bpError && blockedPeriods.length > 0 ? (
            <div className="admin-schedule__table-wrap">
              <table className="admin-schedule__table">
                <thead>
                  <tr>
                    <th scope="col">Staff</th>
                    <th scope="col">Start</th>
                    <th scope="col">End</th>
                    <th scope="col">Reason</th>
                    <th scope="col">Block type</th>
                    {manage ? <th scope="col">Actions</th> : null}
                  </tr>
                </thead>
                <tbody>
                  {blockedPeriods.map((row) => (
                    <tr key={row.id}>
                      <td>{staffLabel(row.staff_id, staffById)}</td>
                      <td>{formatDateTime(row.starts_at)}</td>
                      <td>{formatDateTime(row.ends_at)}</td>
                      <td>{row.reason ?? '—'}</td>
                      <td>{row.block_type.replace('_', ' ')}</td>
                      {manage ? (
                        <td className="admin-schedule__actions">
                          <button
                            type="button"
                            className="btn btn--secondary btn--compact"
                            onClick={() => startEdit(row)}
                            disabled={bpSaving}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="btn btn--secondary btn--compact"
                            onClick={() => void handleDeleteBlocked(row)}
                            disabled={bpSaving}
                          >
                            Delete
                          </button>
                        </td>
                      ) : null}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      </div>
    </AdminLayout>
  )
}
