import {
  DeleteOutlined,
  EditOutlined,
  LeftOutlined,
  PlusOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { Button, Form, Input, Modal, Select, Space, Tag, Typography, theme as antTheme } from 'antd';
import { useEffect, useRef, useState } from 'react';

import { useAuthStore } from '../auth/store';
import type { Role } from '../auth/types';

// ─── Constants ──────────────────────────────────────────────────────────────

const MONTHS_RU = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
];
const MONTHS_RU_GEN = [
  'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
];
const WEEKDAYS_SHORT = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
const WEEKDAYS_LONG = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'];

const ROLE_ACCENT: Record<Role, string> = {
  super_admin: '#E8B86D',
  franchisee: '#5B9BD5',
  point_manager: '#7CCFA2',
  staff: '#B47FDB',
};

const HOUR_OPTIONS = Array.from({ length: 24 }, (_, h) => ({
  value: h,
  label: String(h).padStart(2, '0') + ':00',
}));

// ─── Types ───────────────────────────────────────────────────────────────────

interface DiaryEvent {
  id: string;
  title: string;
  description: string;
  date: string;
  startHour: number;
  endHour: number;
  color: string;
}

interface EventFormValues {
  title: string;
  description?: string;
  startHour: number;
  endHour: number;
}

type CalendarView = 'year' | 'month' | 'day';

// ─── Helpers ─────────────────────────────────────────────────────────────────

function toDateKey(year: number, month: number, day: number): string {
  return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

function getMonthGrid(year: number, month: number): (number | null)[][] {
  const firstDow = new Date(year, month, 1).getDay();
  const offset = (firstDow + 6) % 7;
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells: (number | null)[] = [
    ...Array<null>(offset).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);
  const weeks: (number | null)[][] = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));
  return weeks;
}

function getDayOfWeek(year: number, month: number, day: number): number {
  return (new Date(year, month, day).getDay() + 6) % 7;
}

function daysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

// ─── Component ───────────────────────────────────────────────────────────────

export function DiaryPage() {
  const { token } = antTheme.useToken();
  const userId = useAuthStore((s) => s.user?.id) ?? 'anonymous';
  const role = useAuthStore((s) => s.role) ?? 'staff';

  const today = new Date();
  const todayY = today.getFullYear();
  const todayM = today.getMonth();
  const todayD = today.getDate();

  const [view, setView] = useState<CalendarView>('year');
  const [displayYear, setDisplayYear] = useState(todayY);
  const [selMonth, setSelMonth] = useState(todayM);
  const [selDay, setSelDay] = useState(todayD);
  const [events, setEvents] = useState<Record<string, DiaryEvent[]>>({});
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingEvt, setEditingEvt] = useState<DiaryEvent | null>(null);
  const [preHour, setPreHour] = useState(9);
  const [form] = Form.useForm<EventFormValues>();
  const timelineRef = useRef<HTMLDivElement>(null);

  const storageKey = `japonica_diary_${userId}`;
  const accent = ROLE_ACCENT[role] ?? '#E8B86D';

  // Load/save events
  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) setEvents(JSON.parse(raw) as Record<string, DiaryEvent[]>);
    } catch { /* ignore */ }
  }, [storageKey]);

  const persistEvents = (next: Record<string, DiaryEvent[]>) => {
    setEvents(next);
    localStorage.setItem(storageKey, JSON.stringify(next));
  };

  // Scroll timeline to current hour on day view open
  useEffect(() => {
    if (view === 'day' && timelineRef.current) {
      const hour = today.getHours();
      timelineRef.current.scrollTop = Math.max(0, (hour - 2)) * 64;
    }
  }, [view]); // eslint-disable-line react-hooks/exhaustive-deps

  const eventsOn = (y: number, m: number, d: number) => events[toDateKey(y, m, d)] ?? [];

  // ── Modal helpers ──────────────────────────────────────────────────────────

  const openAdd = (hour: number) => {
    setEditingEvt(null);
    setPreHour(hour);
    form.setFieldsValue({ title: '', description: '', startHour: hour, endHour: Math.min(hour + 1, 23) });
    setIsModalOpen(true);
  };

  const openEdit = (evt: DiaryEvent) => {
    setEditingEvt(evt);
    form.setFieldsValue({
      title: evt.title,
      description: evt.description,
      startHour: evt.startHour,
      endHour: evt.endHour,
    });
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setEditingEvt(null);
    form.resetFields();
  };

  const handleSave = (vals: EventFormValues) => {
    const key = toDateKey(displayYear, selMonth, selDay);
    const cur = events[key] ?? [];
    let next: DiaryEvent[];
    if (editingEvt) {
      next = cur.map((e) =>
        e.id === editingEvt.id
          ? { ...e, title: vals.title, description: vals.description ?? '', startHour: vals.startHour, endHour: vals.endHour }
          : e,
      );
    } else {
      next = [
        ...cur,
        {
          id: `${Date.now()}-${Math.random()}`,
          title: vals.title,
          description: vals.description ?? '',
          date: key,
          startHour: vals.startHour,
          endHour: vals.endHour,
          color: accent,
        },
      ];
    }
    persistEvents({ ...events, [key]: next });
    closeModal();
  };

  const handleDelete = (id: string) => {
    const key = toDateKey(displayYear, selMonth, selDay);
    persistEvents({ ...events, [key]: (events[key] ?? []).filter((e) => e.id !== id) });
    closeModal();
  };

  // ── Month navigation ────────────────────────────────────────────────────────

  const prevMonth = () => {
    if (selMonth === 0) { setDisplayYear((y) => y - 1); setSelMonth(11); }
    else setSelMonth((m) => m - 1);
  };

  const nextMonth = () => {
    if (selMonth === 11) { setDisplayYear((y) => y + 1); setSelMonth(0); }
    else setSelMonth((m) => m + 1);
  };

  // ─── Year View ───────────────────────────────────────────────────────────────

  const renderYearView = () => (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
        <Button
          type="text"
          icon={<LeftOutlined />}
          onClick={() => setDisplayYear((y) => y - 1)}
          style={{ color: token.colorText }}
        />
        <Typography.Title level={1} style={{ margin: 0, color: '#FF3B30', fontWeight: 700 }}>
          {displayYear}
        </Typography.Title>
        <Button
          type="text"
          icon={<RightOutlined />}
          onClick={() => setDisplayYear((y) => y + 1)}
          style={{ color: token.colorText }}
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        {MONTHS_RU.map((name, month) => {
          const weeks = getMonthGrid(displayYear, month);
          const isCurMonth = displayYear === todayY && month === todayM;

          return (
            <div
              key={month}
              onClick={() => { setSelMonth(month); setView('month'); }}
              style={{
                cursor: 'pointer',
                borderRadius: 14,
                padding: '10px 10px 8px',
                background: isCurMonth ? `${accent}12` : `${token.colorBgContainer}`,
                border: `1px solid ${isCurMonth ? `${accent}40` : token.colorBorderSecondary ?? token.colorBorder}`,
                transition: 'background 0.15s',
              }}
            >
              <Typography.Text
                strong
                style={{
                  color: isCurMonth ? accent : token.colorText,
                  fontSize: 13,
                  display: 'block',
                  marginBottom: 6,
                }}
              >
                {name}
              </Typography.Text>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 1 }}>
                {['П','В','С','Ч','П','С','В'].map((d, i) => (
                  <div key={i} style={{ textAlign: 'center', fontSize: 8, color: token.colorTextTertiary, lineHeight: '13px' }}>
                    {d}
                  </div>
                ))}
                {weeks.flat().map((day, i) => {
                  const isToday = isCurMonth && day === todayD;
                  const hasEvt = day ? eventsOn(displayYear, month, day).length > 0 : false;
                  return (
                    <div key={i} style={{ textAlign: 'center' }}>
                      {day != null ? (
                        <>
                          <div
                            style={{
                              width: 15, height: 15, borderRadius: '50%',
                              background: isToday ? '#FF3B30' : 'transparent',
                              display: 'flex', alignItems: 'center', justifyContent: 'center',
                              margin: '0 auto',
                            }}
                          >
                            <span style={{ fontSize: 9, color: isToday ? '#fff' : token.colorTextSecondary, lineHeight: '15px' }}>
                              {day}
                            </span>
                          </div>
                          {hasEvt && (
                            <div style={{ width: 3, height: 3, borderRadius: '50%', background: accent, margin: '1px auto 0' }} />
                          )}
                        </>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );

  // ─── Month View ──────────────────────────────────────────────────────────────

  const renderMonthView = () => {
    const weeks = getMonthGrid(displayYear, selMonth);
    const isCurYM = displayYear === todayY && selMonth === todayM;

    return (
      <div>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
          <Button
            type="text"
            icon={<LeftOutlined />}
            onClick={() => setView('year')}
            style={{ color: accent, fontWeight: 600 }}
          >
            {displayYear}
          </Button>
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Button type="text" icon={<LeftOutlined />} onClick={prevMonth} style={{ color: token.colorText }} />
            <Typography.Title level={2} style={{ margin: 0, color: token.colorText, fontWeight: 700 }}>
              {MONTHS_RU[selMonth]}
            </Typography.Title>
            <Button type="text" icon={<RightOutlined />} onClick={nextMonth} style={{ color: token.colorText }} />
          </div>
        </div>

        {/* Weekday headers */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', marginBottom: 4 }}>
          {WEEKDAYS_SHORT.map((d, i) => (
            <div key={i} style={{ textAlign: 'center', fontSize: 13, color: token.colorTextTertiary, padding: '4px 0' }}>
              {d}
            </div>
          ))}
        </div>

        {/* Day grid */}
        <div style={{ border: `1px solid ${token.colorBorder}`, borderRadius: 12, overflow: 'hidden' }}>
          {weeks.map((week, wi) => (
            <div
              key={wi}
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(7, 1fr)',
                borderBottom: wi < weeks.length - 1 ? `1px solid ${token.colorBorder}` : 'none',
              }}
            >
              {week.map((day, di) => {
                const isToday = isCurYM && day === todayD;
                const isWeekend = di >= 5;
                const evts = day ? eventsOn(displayYear, selMonth, day) : [];

                return (
                  <div
                    key={di}
                    onClick={() => { if (day) { setSelDay(day); setView('day'); } }}
                    style={{
                      minHeight: 82,
                      padding: '6px 5px',
                      cursor: day ? 'pointer' : 'default',
                      borderRight: di < 6 ? `1px solid ${token.colorBorder}` : 'none',
                      background: 'transparent',
                      transition: 'background 0.1s',
                    }}
                    onMouseEnter={(e) => { if (day) (e.currentTarget as HTMLDivElement).style.background = `${token.colorBgElevated}`; }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
                  >
                    {day != null ? (
                      <>
                        <div
                          style={{
                            width: 28, height: 28, borderRadius: '50%',
                            background: isToday ? '#FF3B30' : 'transparent',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            marginBottom: 3,
                          }}
                        >
                          <Typography.Text
                            style={{
                              fontSize: 14,
                              fontWeight: isToday ? 700 : 400,
                              color: isToday ? '#fff' : (isWeekend ? token.colorTextTertiary : token.colorText),
                            }}
                          >
                            {day}
                          </Typography.Text>
                        </div>
                        {evts.slice(0, 3).map((e, ei) => (
                          <div
                            key={ei}
                            style={{
                              fontSize: 10, borderRadius: 4,
                              background: e.color + '28',
                              borderLeft: `2px solid ${e.color}`,
                              color: e.color,
                              padding: '1px 4px',
                              marginBottom: 2,
                              overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis',
                            }}
                          >
                            {String(e.startHour).padStart(2,'0')}:00 {e.title}
                          </div>
                        ))}
                        {evts.length > 3 && (
                          <Typography.Text style={{ fontSize: 10, color: token.colorTextTertiary }}>
                            +{evts.length - 3} ещё
                          </Typography.Text>
                        )}
                      </>
                    ) : null}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    );
  };

  // ─── Day View ────────────────────────────────────────────────────────────────

  const renderDayView = () => {
    const key = toDateKey(displayYear, selMonth, selDay);
    const dayEvts = events[key] ?? [];
    const isToday = displayYear === todayY && selMonth === todayM && selDay === todayD;
    const dow = getDayOfWeek(displayYear, selMonth, selDay);
    const curHour = today.getHours();
    const curMin = today.getMinutes();
    const curTop = isToday ? curHour * 64 + (curMin / 60) * 64 : -1;
    const maxDay = daysInMonth(displayYear, selMonth);
    const weekStart = selDay - dow;

    return (
      <div>
        {/* Header row */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <Button
            type="text"
            icon={<LeftOutlined />}
            onClick={() => setView('month')}
            style={{ color: accent, fontWeight: 600 }}
          >
            {MONTHS_RU[selMonth]}
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            size="small"
            onClick={() => openAdd(isToday ? curHour : 9)}
          >
            Добавить
          </Button>
        </div>

        {/* Week strip */}
        <div
          style={{
            display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)',
            marginBottom: 6,
            paddingBottom: 8,
            borderBottom: `1px solid ${token.colorBorder}`,
          }}
        >
          {WEEKDAYS_SHORT.map((d, i) => {
            const num = weekStart + i;
            const valid = num >= 1 && num <= maxDay;
            const isSel = i === dow;
            const isTodayCell = isToday && isSel;

            return (
              <div
                key={i}
                style={{ textAlign: 'center', cursor: valid ? 'pointer' : 'default' }}
                onClick={() => { if (valid) setSelDay(num); }}
              >
                <div style={{ fontSize: 11, color: token.colorTextTertiary, marginBottom: 3 }}>{d}</div>
                <div
                  style={{
                    width: 32, height: 32, borderRadius: '50%', margin: '0 auto',
                    background: isTodayCell ? '#FF3B30' : (isSel ? token.colorBgElevated : 'transparent'),
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}
                >
                  <span style={{
                    fontSize: 15,
                    fontWeight: isSel ? 700 : 400,
                    color: isTodayCell ? '#fff' : (valid ? token.colorText : token.colorTextTertiary),
                  }}>
                    {valid ? num : ''}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Day title */}
        <Typography.Text
          style={{
            display: 'block', textAlign: 'center', fontSize: 15,
            fontWeight: 500, color: token.colorText, marginBottom: 10,
          }}
        >
          {WEEKDAYS_LONG[dow]} — {selDay} {MONTHS_RU_GEN[selMonth]} {displayYear} г.
        </Typography.Text>

        {/* Timeline */}
        <div
          ref={timelineRef}
          style={{ position: 'relative', overflowY: 'auto', maxHeight: 'calc(100vh - 290px)' }}
        >
          {/* Current time indicator */}
          {curTop >= 0 && (
            <div
              style={{
                position: 'absolute', left: 52, right: 0, top: curTop,
                height: 2, background: '#FF3B30', zIndex: 10, borderRadius: 1, pointerEvents: 'none',
              }}
            >
              <div
                style={{
                  position: 'absolute', left: -52, top: -9,
                  background: '#FF3B30', color: '#fff', fontSize: 11,
                  padding: '2px 6px', borderRadius: 8, fontWeight: 700,
                  whiteSpace: 'nowrap',
                }}
              >
                {String(curHour).padStart(2,'0')}:{String(curMin).padStart(2,'0')}
              </div>
            </div>
          )}

          {Array.from({ length: 24 }, (_, hour) => {
            const slotEvts = dayEvts.filter((e) => e.startHour <= hour && e.endHour > hour);

            return (
              <div
                key={hour}
                onClick={() => openAdd(hour)}
                style={{
                  height: 64, display: 'flex', cursor: 'pointer',
                  borderTop: `1px solid ${token.colorBorder}`,
                  position: 'relative',
                }}
              >
                {/* Hour label */}
                <div style={{ width: 52, paddingRight: 8, paddingTop: 4, textAlign: 'right', flexShrink: 0 }}>
                  <Typography.Text style={{ fontSize: 12, color: token.colorTextTertiary }}>
                    {String(hour).padStart(2,'0')}:00
                  </Typography.Text>
                </div>

                {/* Events */}
                <div style={{ flex: 1, position: 'relative' }}>
                  {slotEvts
                    .filter((e) => e.startHour === hour)
                    .map((evt, ei) => (
                      <div
                        key={ei}
                        onClick={(ev) => { ev.stopPropagation(); openEdit(evt); }}
                        style={{
                          position: 'absolute',
                          left: 4 + ei * 8, right: 4,
                          top: 3,
                          height: Math.max(1, evt.endHour - evt.startHour) * 64 - 6,
                          background: evt.color + '22',
                          borderLeft: `3px solid ${evt.color}`,
                          borderRadius: 6,
                          padding: '4px 8px',
                          cursor: 'pointer',
                          zIndex: 5 + ei,
                          overflow: 'hidden',
                        }}
                      >
                        <Typography.Text style={{ fontSize: 12, fontWeight: 600, color: evt.color, display: 'block' }}>
                          {evt.title}
                        </Typography.Text>
                        <Typography.Text style={{ fontSize: 11, color: token.colorTextSecondary }}>
                          {String(evt.startHour).padStart(2,'0')}:00 – {String(evt.endHour).padStart(2,'0')}:00
                        </Typography.Text>
                      </div>
                    ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  // ─── Render ──────────────────────────────────────────────────────────────────

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      {/* Page header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <Typography.Title level={3} style={{ margin: 0, color: token.colorText }}>
            Ежедневник
          </Typography.Title>
          <Typography.Text style={{ color: token.colorTextSecondary }}>
            Личные задачи и события
          </Typography.Text>
        </div>
        <Tag
          style={{
            background: accent + '1A',
            borderColor: accent + '40',
            color: accent,
            borderRadius: 20,
            padding: '2px 12px',
            fontSize: 12,
          }}
        >
          {role.replace('_', ' ')}
        </Tag>
      </div>

      {/* Views */}
      {view === 'year' && renderYearView()}
      {view === 'month' && renderMonthView()}
      {view === 'day' && renderDayView()}

      {/* Event modal */}
      <Modal
        title={
          <Space>
            {editingEvt ? <EditOutlined style={{ color: accent }} /> : <PlusOutlined style={{ color: accent }} />}
            <span>{editingEvt ? 'Редактировать событие' : 'Новое событие'}</span>
          </Space>
        }
        open={isModalOpen}
        onCancel={closeModal}
        footer={null}
        width={420}
      >
        <Form form={form} layout="vertical" onFinish={handleSave} style={{ marginTop: 8 }}>
          <Form.Item
            name="title"
            label="Название"
            rules={[{ required: true, message: 'Введите название события' }]}
          >
            <Input placeholder="Название события" autoFocus />
          </Form.Item>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <Form.Item name="startHour" label="Начало" rules={[{ required: true }]}>
              <Select options={HOUR_OPTIONS} onChange={(v: number) => {
                const end = form.getFieldValue('endHour') as number | undefined;
                if (end === undefined || end <= v) {
                  form.setFieldValue('endHour', Math.min(v + 1, 23));
                }
              }} />
            </Form.Item>
            <Form.Item name="endHour" label="Конец" rules={[{ required: true }]}>
              <Select options={HOUR_OPTIONS} />
            </Form.Item>
          </div>

          <Form.Item name="description" label="Описание (необязательно)">
            <Input.TextArea rows={3} placeholder="Дополнительные заметки..." />
          </Form.Item>

          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
            {editingEvt ? (
              <Button
                danger
                icon={<DeleteOutlined />}
                onClick={() => handleDelete(editingEvt.id)}
              >
                Удалить
              </Button>
            ) : <div />}
            <Space>
              <Button onClick={closeModal}>Отмена</Button>
              <Button type="primary" htmlType="submit">Сохранить</Button>
            </Space>
          </div>
        </Form>
      </Modal>
    </div>
  );
}
