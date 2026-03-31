import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  DatePicker,
  Empty,
  Form,
  Input,
  List,
  Modal,
  Progress,
  Row,
  Select,
  Space,
  Spin,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
  Drawer,
} from 'antd';
import { PlusOutlined, CloseOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';

import { apiClient } from '../api/client';
import { useAuthStore } from '../auth/store';
import { ensureArray } from '../utils/ensureArray';

type FranchiseeStatus =
  | 'lead'
  | 'negotiation'
  | 'contract'
  | 'training'
  | 'setup'
  | 'open'
  | 'active'
  | 'terminated';

type TaskStatus = 'pending' | 'in_progress' | 'done' | 'skipped';

interface FranchiseeItem {
  id: string;
  company_name: string;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  status: FranchiseeStatus;
  responsible_owner_id: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  points_count: number;
}

interface StageProgress {
  stage: string;
  total: number;
  done: number;
  percent: number;
}

interface TaskItem {
  id: string;
  franchisee_id: string;
  title: string;
  stage: FranchiseeStatus;
  status: TaskStatus;
  due_date: string | null;
  created_at: string | null;
  completed_at: string | null;
}

interface TaskListResponse {
  tasks: TaskItem[];
  stage_progress: StageProgress;
}

interface NoteItem {
  id: string;
  text: string;
  author: string | null;
  created_at: string;
}

interface PointItem {
  id: string;
  name: string;
  address: string;
  is_active: boolean;
  franchisee_id: string | null;
}

const STATUS_ORDER: FranchiseeStatus[] = [
  'lead',
  'negotiation',
  'contract',
  'training',
  'setup',
  'open',
  'active',
  'terminated',
];

const STATUS_LABELS: Record<FranchiseeStatus, string> = {
  lead: 'Лид',
  negotiation: 'Переговоры',
  contract: 'Договор',
  training: 'Обучение',
  setup: 'Настройка',
  open: 'Открыт',
  active: 'Активен',
  terminated: 'Закрыт',
};

const STATUS_COLORS: Record<FranchiseeStatus, string> = {
  lead: 'default',
  negotiation: 'blue',
  contract: 'gold',
  training: 'geekblue',
  setup: 'purple',
  open: 'cyan',
  active: 'green',
  terminated: 'red',
};

const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  pending: 'В ожидании',
  in_progress: 'В работе',
  done: 'Готово',
  skipped: 'Пропущено',
};

const TASK_STATUS_OPTIONS = Object.entries(TASK_STATUS_LABELS).map(([value, label]) => ({
  value: value as TaskStatus,
  label,
}));

function authHeader(token: string | null): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function fetchFranchisees(token: string | null): Promise<FranchiseeItem[]> {
  const { data } = await apiClient.get<FranchiseeItem[]>('/v1/franchisees', {
    headers: authHeader(token),
  });
  return data;
}

async function fetchFranchiseeDetail(
  franchiseeId: string,
  token: string | null,
): Promise<FranchiseeItem> {
  const { data } = await apiClient.get<FranchiseeItem>(`/v1/franchisees/${franchiseeId}`, {
    headers: authHeader(token),
  });
  return data;
}

async function fetchFranchiseeTasks(
  franchiseeId: string,
  token: string | null,
): Promise<TaskListResponse> {
  const { data } = await apiClient.get<TaskListResponse>(`/v1/franchisees/${franchiseeId}/tasks`, {
    headers: authHeader(token),
  });
  return data;
}

async function fetchFranchiseeNotes(
  franchiseeId: string,
  token: string | null,
): Promise<NoteItem[]> {
  const { data } = await apiClient.get<NoteItem[]>(`/v1/franchisees/${franchiseeId}/notes`, {
    headers: authHeader(token),
  });
  return data;
}

async function fetchFranchiseePoints(
  franchiseeId: string,
  token: string | null,
): Promise<PointItem[]> {
  const { data } = await apiClient.get<PointItem[]>(`/v1/franchisees/${franchiseeId}/points`, {
    headers: authHeader(token),
  });
  return data;
}

async function fetchPoints(token: string | null): Promise<PointItem[]> {
  const { data } = await apiClient.get<PointItem[]>('/v1/points', {
    headers: authHeader(token),
  });
  return data;
}

function formatApiError(error: unknown, fallback: string): string {
  if (typeof error === 'string') {
    return error;
  }

  if (error && typeof error === 'object') {
    const candidate = error as {
      message?: string;
      detail?: string;
      response?: { data?: { detail?: string; message?: string } };
    };
    return (
      candidate.response?.data?.detail ??
      candidate.response?.data?.message ??
      candidate.detail ??
      candidate.message ??
      fallback
    );
  }

  return fallback;
}

function FranchiseeCard({
  franchisee,
  progressPercent,
  onOpen,
}: {
  franchisee: FranchiseeItem;
  progressPercent: number;
  onOpen: (item: FranchiseeItem) => void;
}) {
  return (
    <Card
      size="small"
      hoverable
      onClick={() => onOpen(franchisee)}
      styles={{ body: { padding: 14 } }}
      style={{ borderRadius: 10 }}
    >
      <Space direction="vertical" size={8} style={{ width: '100%' }}>
        <Space style={{ justifyContent: 'space-between', width: '100%' }} align="start">
          <Typography.Text strong>{franchisee.company_name}</Typography.Text>
          <Tag color={STATUS_COLORS[franchisee.status]}>{STATUS_LABELS[franchisee.status]}</Tag>
        </Space>
        <Typography.Text type="secondary">
          {franchisee.contact_name ?? 'Без контакта'}
        </Typography.Text>
        <Typography.Text type="secondary">
          Создан {dayjs(franchisee.created_at).format('DD.MM.YYYY')}
        </Typography.Text>
        <Progress percent={progressPercent} size="small" />
      </Space>
    </Card>
  );
}

export function FranchiseeKanbanPage() {
  const token = useAuthStore((state) => state.token);
  const role = useAuthStore((state) => state.role);
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();
  const [selectedFranchiseeId, setSelectedFranchiseeId] = useState<string | null>(null);
  const [selectedPreview, setSelectedPreview] = useState<FranchiseeItem | null>(null);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createInitialStage, setCreateInitialStage] = useState<FranchiseeStatus>('lead');
  const [isCreateTaskOpen, setIsCreateTaskOpen] = useState(false);
  const [addForm] = Form.useForm();
  const [noteForm] = Form.useForm();
  const [attachForm] = Form.useForm();
  const [createPointForm] = Form.useForm();
  const [createTaskForm] = Form.useForm();

  const franchiseesQuery = useQuery({
    queryKey: ['franchisee-board', token],
    queryFn: () => fetchFranchisees(token),
    retry: false,
    enabled: role === 'super_admin',
    select: (data) => ensureArray<FranchiseeItem>(data),
  });

  const franchisees = ensureArray<FranchiseeItem>(franchiseesQuery.data);

  const progressMapQuery = useQuery({
    queryKey: ['franchisee-progress', franchisees.map((item) => item.id)],
    enabled: role === 'super_admin' && franchisees.length > 0,
    retry: false,
    queryFn: async () => {
      const settled = await Promise.allSettled(
        franchisees.map(async (item) => {
          const data = await fetchFranchiseeTasks(item.id, token);
          return [item.id, data.stage_progress.percent] as const;
        }),
      );

      const successfulEntries = settled.flatMap((result) =>
        result.status === 'fulfilled' ? [result.value] : [],
      );

      return Object.fromEntries(successfulEntries);
    },
  });

  const selectedDetailQuery = useQuery({
    queryKey: ['franchisee-detail', selectedFranchiseeId, token],
    queryFn: () => fetchFranchiseeDetail(selectedFranchiseeId!, token),
    enabled: Boolean(selectedFranchiseeId),
    retry: false,
  });

  const detailTasksQuery = useQuery({
    queryKey: ['franchisee-tasks', selectedFranchiseeId, token],
    queryFn: () => fetchFranchiseeTasks(selectedFranchiseeId!, token),
    enabled: Boolean(selectedFranchiseeId),
    retry: false,
  });

  const detailNotesQuery = useQuery({
    queryKey: ['franchisee-notes', selectedFranchiseeId, token],
    queryFn: () => fetchFranchiseeNotes(selectedFranchiseeId!, token),
    enabled: Boolean(selectedFranchiseeId),
    retry: false,
    select: (data) => ensureArray<NoteItem>(data),
  });

  const detailPointsQuery = useQuery({
    queryKey: ['franchisee-points', selectedFranchiseeId, token],
    queryFn: () => fetchFranchiseePoints(selectedFranchiseeId!, token),
    enabled: Boolean(selectedFranchiseeId),
    retry: false,
    select: (data) => ensureArray<PointItem>(data),
  });

  const allPointsQuery = useQuery({
    queryKey: ['franchisee-all-points', token],
    queryFn: () => fetchPoints(token),
    enabled: role === 'super_admin',
    retry: false,
    select: (data) => (Array.isArray(data) ? data : []),
  });

  const createFranchiseeMutation = useMutation({
    mutationFn: async (values: {
      company_name: string;
      contact_name?: string;
      contact_email?: string;
      contact_phone?: string;
      _initial_status?: FranchiseeStatus;
    }) => {
      const { _initial_status, ...payload } = values;
      const resp = await apiClient.post<FranchiseeItem>('/v1/franchisees', payload, {
        headers: authHeader(token),
      });
      if (_initial_status && _initial_status !== 'lead') {
        await apiClient.patch(
          `/v1/franchisees/${resp.data.id}/stage`,
          { status: _initial_status },
          { headers: authHeader(token) },
        );
      }
      return resp;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['franchisee-board'] });
      setIsCreateOpen(false);
      setCreateInitialStage('lead');
      addForm.resetFields();
      void messageApi.success('Франчайзи создан');
    },
    onError: (error) => {
      void messageApi.error(formatApiError(error, 'Не удалось создать франчайзи'));
    },
  });

  const stageMutation = useMutation({
    mutationFn: async ({
      franchiseeId,
      nextStatus,
    }: {
      franchiseeId: string;
      nextStatus: FranchiseeStatus;
    }) =>
      apiClient.patch(
        `/v1/franchisees/${franchiseeId}/stage`,
        { status: nextStatus },
        { headers: authHeader(token) },
      ),
    onSuccess: async (_data, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['franchisee-board'] }),
        queryClient.invalidateQueries({ queryKey: ['franchisee-detail', variables.franchiseeId] }),
        queryClient.invalidateQueries({ queryKey: ['franchisee-tasks', variables.franchiseeId] }),
        queryClient.invalidateQueries({ queryKey: ['franchisee-progress'] }),
      ]);
      void messageApi.success('Стадия обновлена');
    },
    onError: (error) => {
      void messageApi.error(formatApiError(error, 'Не удалось обновить стадию'));
    },
  });

  const taskMutation = useMutation({
    mutationFn: async ({
      franchiseeId,
      taskId,
      status,
    }: {
      franchiseeId: string;
      taskId: string;
      status: TaskStatus;
    }) =>
      apiClient.patch(
        `/v1/franchisees/${franchiseeId}/tasks/${taskId}`,
        { status },
        { headers: authHeader(token) },
      ),
    onSuccess: async (_data, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['franchisee-detail', variables.franchiseeId] }),
        queryClient.invalidateQueries({ queryKey: ['franchisee-tasks', variables.franchiseeId] }),
        queryClient.invalidateQueries({ queryKey: ['franchisee-progress'] }),
      ]);
      void messageApi.success('Задача обновлена');
    },
    onError: (error) => {
      void messageApi.error(formatApiError(error, 'Не удалось обновить задачу'));
    },
  });

  const noteMutation = useMutation({
    mutationFn: async ({
      franchiseeId,
      text,
    }: {
      franchiseeId: string;
      text: string;
    }) =>
      apiClient.post(`/v1/franchisees/${franchiseeId}/notes`, { text }, {
        headers: authHeader(token),
      }),
    onSuccess: async (_data, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['franchisee-detail', variables.franchiseeId] }),
        queryClient.invalidateQueries({ queryKey: ['franchisee-notes', variables.franchiseeId] }),
      ]);
      noteForm.resetFields();
      void messageApi.success('Заметка добавлена');
    },
    onError: (error) => {
      void messageApi.error(formatApiError(error, 'Не удалось добавить заметку'));
    },
  });

  const attachPointMutation = useMutation({
    mutationFn: async ({
      franchiseeId,
      pointId,
    }: {
      franchiseeId: string;
      pointId: string;
    }) =>
      apiClient.post(
        `/v1/franchisees/${franchiseeId}/points`,
        { point_id: pointId },
        {
          headers: authHeader(token),
        },
      ),
    onSuccess: async (_data, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['franchisee-detail', variables.franchiseeId] }),
        queryClient.invalidateQueries({ queryKey: ['franchisee-points', variables.franchiseeId] }),
        queryClient.invalidateQueries({ queryKey: ['franchisee-board'] }),
        queryClient.invalidateQueries({ queryKey: ['franchisee-all-points'] }),
      ]);
      attachForm.resetFields();
      void messageApi.success('Точка привязана');
    },
    onError: (error) => {
      void messageApi.error(formatApiError(error, 'Не удалось привязать точку'));
    },
  });

  const createPointMutation = useMutation({
    mutationFn: async ({
      franchiseeId,
      name,
      address,
    }: {
      franchiseeId: string;
      name: string;
      address: string;
    }) =>
      apiClient.post(
        `/v1/franchisees/${franchiseeId}/points`,
        { name, address },
        {
          headers: authHeader(token),
        },
      ),
    onSuccess: async (_data, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['franchisee-detail', variables.franchiseeId] }),
        queryClient.invalidateQueries({ queryKey: ['franchisee-points', variables.franchiseeId] }),
        queryClient.invalidateQueries({ queryKey: ['franchisee-board'] }),
        queryClient.invalidateQueries({ queryKey: ['franchisee-all-points'] }),
      ]);
      createPointForm.resetFields();
      void messageApi.success('Точка создана и привязана');
    },
    onError: (error) => {
      void messageApi.error(formatApiError(error, 'Не удалось создать точку'));
    },
  });

  const createTaskMutation = useMutation({
    mutationFn: async ({
      franchiseeId,
      title,
      stage,
      due_date,
    }: {
      franchiseeId: string;
      title: string;
      stage: FranchiseeStatus;
      due_date?: string;
    }) =>
      apiClient.post(
        `/v1/franchisees/${franchiseeId}/tasks`,
        { title, stage, due_date: due_date ?? null },
        { headers: authHeader(token) },
      ),
    onSuccess: async (_data, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['franchisee-tasks', variables.franchiseeId] }),
        queryClient.invalidateQueries({ queryKey: ['franchisee-progress'] }),
      ]);
      setIsCreateTaskOpen(false);
      createTaskForm.resetFields();
      void messageApi.success('Задача добавлена');
    },
    onError: (error) => {
      void messageApi.error(formatApiError(error, 'Не удалось добавить задачу'));
    },
  });

  const detachPointMutation = useMutation({
    mutationFn: async ({
      franchiseeId,
      pointId,
    }: {
      franchiseeId: string;
      pointId: string;
    }) =>
      apiClient.delete(`/v1/franchisees/${franchiseeId}/points/${pointId}`, {
        headers: authHeader(token),
      }),
    onSuccess: async (_data, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['franchisee-detail', variables.franchiseeId] }),
        queryClient.invalidateQueries({ queryKey: ['franchisee-points', variables.franchiseeId] }),
        queryClient.invalidateQueries({ queryKey: ['franchisee-board'] }),
        queryClient.invalidateQueries({ queryKey: ['franchisee-all-points'] }),
      ]);
      void messageApi.success('Точка отвязана');
    },
    onError: (error) => {
      void messageApi.error(formatApiError(error, 'Не удалось отвязать точку'));
    },
  });

  const columns = useMemo(
    () =>
      STATUS_ORDER.map((status) => ({
        status,
        items: franchisees.filter((item) => item.status === status),
      })),
    [franchisees],
  );

  const progressMap =
    progressMapQuery.data && typeof progressMapQuery.data === 'object' && !Array.isArray(progressMapQuery.data)
      ? progressMapQuery.data
      : {};
  const detailTasks = ensureArray<TaskItem>(detailTasksQuery.data?.tasks);
  const detailProgress = detailTasksQuery.data?.stage_progress;
  const detailNotes = ensureArray<NoteItem>(detailNotesQuery.data);
  const detailPoints = ensureArray<PointItem>(detailPointsQuery.data);
  const allPoints = ensureArray<PointItem>(allPointsQuery.data);
  const selectedFranchisee = selectedDetailQuery.data ?? selectedPreview;

  useEffect(() => {
    if (selectedDetailQuery.data) {
      setSelectedPreview(selectedDetailQuery.data);
    }
  }, [selectedDetailQuery.data]);

  if (role !== 'super_admin') {
    return (
      <Card>
        <Typography.Title level={4}>Доска франчайзи</Typography.Title>
        <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
          Этот раздел доступен только для суперадминистратора.
        </Typography.Paragraph>
      </Card>
    );
  }

  const nextStage =
    selectedFranchisee && selectedFranchisee.status !== 'terminated'
      ? STATUS_ORDER[STATUS_ORDER.indexOf(selectedFranchisee.status) + 1] ?? null
      : null;

  const attachOptions = allPoints
    .filter((point) => !detailPoints.some((attached) => attached.id === point.id))
    .map((point) => ({
      value: point.id,
      label: `${point.name} — ${point.address}`,
    }));

  return (
    <Space direction="vertical" size={24} style={{ width: '100%' }}>
      {contextHolder}
      <Space style={{ justifyContent: 'space-between', width: '100%' }} wrap>
        <div>
          <Typography.Title level={3} style={{ marginBottom: 4 }}>
            Воронка франчайзи
          </Typography.Title>
          <Typography.Text type="secondary">
            Доска стадий, заметки, чеклист и связанные точки.
          </Typography.Text>
        </div>
        <Button type="primary" onClick={() => setIsCreateOpen(true)}>
          Добавить франчайзи
        </Button>
      </Space>

      {franchiseesQuery.isError ? (
        <Alert
          type="error"
          message="Не удалось загрузить франчайзи"
          description="Попробуйте обновить страницу или повторить запрос позже."
          showIcon
        />
      ) : franchiseesQuery.isLoading ? (
        <Card>
          <Spin tip="Загрузка франчайзи" />
        </Card>
      ) : (
        <div style={{ display: 'flex', gap: 16, overflowX: 'auto', paddingBottom: 8 }}>
          {columns.map((column) => (
            <div
              key={column.status}
              style={{
                minWidth: 280,
                background: '#f5f5f5',
                borderRadius: 14,
                padding: 12,
              }}
            >
              <Space
                style={{ justifyContent: 'space-between', width: '100%', marginBottom: 12 }}
              >
                <Space size={8}>
                  <Tag color={STATUS_COLORS[column.status]}>{STATUS_LABELS[column.status]}</Tag>
                  <Typography.Text type="secondary">{column.items.length}</Typography.Text>
                </Space>
                <Tooltip title={`Добавить франчайзи в стадию «${STATUS_LABELS[column.status]}»`}>
                  <Button
                    size="small"
                    type="text"
                    icon={<PlusOutlined />}
                    onClick={() => {
                      setCreateInitialStage(column.status);
                      addForm.setFieldValue('initial_status', column.status);
                      setIsCreateOpen(true);
                    }}
                  />
                </Tooltip>
              </Space>

              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                {column.items.length === 0 ? (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Нет франчайзи" />
                ) : (
                  column.items.map((item) => (
                    <FranchiseeCard
                      key={item.id}
                      franchisee={item}
                      progressPercent={progressMap[item.id] ?? 0}
                      onOpen={(value) => {
                        setSelectedFranchiseeId(value.id);
                        setSelectedPreview(value);
                      }}
                    />
                  ))
                )}
              </Space>
            </div>
          ))}
        </div>
      )}

      <Modal
        title="Добавить франчайзи"
        open={isCreateOpen}
        okText="Сохранить"
        cancelText="Отмена"
        onCancel={() => {
          setIsCreateOpen(false);
          setCreateInitialStage('lead');
          addForm.resetFields();
        }}
        onOk={() => addForm.submit()}
        confirmLoading={createFranchiseeMutation.isPending}
      >
        <Form
          form={addForm}
          layout="vertical"
          initialValues={{ initial_status: 'lead' }}
          onFinish={(values: { initial_status: FranchiseeStatus; company_name: string; contact_name?: string; contact_email?: string; contact_phone?: string }) => {
            const { initial_status, ...rest } = values;
            createFranchiseeMutation.mutate({ ...rest, _initial_status: initial_status });
          }}
        >
          <Form.Item label="Стадия" name="initial_status">
            <Select
              options={STATUS_ORDER.map((s) => ({ value: s, label: STATUS_LABELS[s] }))}
            />
          </Form.Item>
          <Form.Item label="Название компании" name="company_name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Контактное лицо" name="contact_name">
            <Input />
          </Form.Item>
          <Form.Item label="Электронная почта" name="contact_email">
            <Input />
          </Form.Item>
          <Form.Item label="Телефон" name="contact_phone">
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="Добавить задачу"
        open={isCreateTaskOpen}
        okText="Сохранить"
        cancelText="Отмена"
        onCancel={() => { setIsCreateTaskOpen(false); createTaskForm.resetFields(); }}
        onOk={() => createTaskForm.submit()}
        confirmLoading={createTaskMutation.isPending}
      >
        <Form
          form={createTaskForm}
          layout="vertical"
          onFinish={(values: { title: string; stage: FranchiseeStatus; due_date?: ReturnType<typeof dayjs> }) => {
            createTaskMutation.mutate({
              franchiseeId: selectedFranchiseeId!,
              title: values.title,
              stage: values.stage,
              due_date: values.due_date ? values.due_date.format('YYYY-MM-DD') : undefined,
            });
          }}
        >
          <Form.Item label="Название задачи" name="title" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Стадия" name="stage" rules={[{ required: true }]}>
            <Select options={STATUS_ORDER.map((s) => ({ value: s, label: STATUS_LABELS[s] }))} />
          </Form.Item>
          <Form.Item label="Срок выполнения" name="due_date">
            <DatePicker style={{ width: '100%' }} format="DD.MM.YYYY" />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        title={
          <Space style={{ justifyContent: 'space-between', width: '100%' }}>
            <Space direction="vertical" size={2}>
              <Typography.Text strong>{selectedFranchisee?.company_name ?? 'Карточка франчайзи'}</Typography.Text>
              {selectedFranchisee ? (
                <Tag color={STATUS_COLORS[selectedFranchisee.status]} style={{ marginTop: 2 }}>
                  {STATUS_LABELS[selectedFranchisee.status]}
                </Tag>
              ) : null}
            </Space>
            <Button
              type="text"
              icon={<CloseOutlined />}
              onClick={() => {
                setSelectedFranchiseeId(null);
                setSelectedPreview(null);
                noteForm.resetFields();
                attachForm.resetFields();
                createPointForm.resetFields();
              }}
            />
          </Space>
        }
        closable={false}
        open={Boolean(selectedFranchiseeId)}
        onClose={() => {
          setSelectedFranchiseeId(null);
          setSelectedPreview(null);
          noteForm.resetFields();
          attachForm.resetFields();
          createPointForm.resetFields();
        }}
        width={520}
        styles={{ body: { padding: 16 } }}
      >
        {!selectedFranchisee ? (
          <Spin tip="Загрузка карточки" />
        ) : (
          <>
            {selectedDetailQuery.isError ? (
              <Alert
                type="error"
                message="Не удалось загрузить свежую карточку франчайзи"
                description="Показываю данные с доски, но они могут быть устаревшими."
                showIcon
                style={{ marginBottom: 16 }}
              />
            ) : null}
            <Tabs
              items={[
                {
                  key: 'overview',
                  label: 'Обзор',
                  children: (
                    <Space direction="vertical" size={16} style={{ width: '100%' }}>
                      <Row gutter={[16, 16]}>
                        <Col xs={24}>
                          <Card size="small">
                            <Space direction="vertical" size={6} style={{ width: '100%' }}>
                              <Typography.Text strong>{selectedFranchisee.company_name}</Typography.Text>
                              <Typography.Text type="secondary">
                                {selectedFranchisee.contact_name ?? 'Нет контакта'}
                              </Typography.Text>
                              <Typography.Text type="secondary">
                                {selectedFranchisee.contact_email ?? 'Почта не указана'}
                              </Typography.Text>
                              <Typography.Text type="secondary">
                                {selectedFranchisee.contact_phone ?? 'Нет телефона'}
                              </Typography.Text>
                            </Space>
                          </Card>
                        </Col>
                        <Col xs={24}>
                          <Card size="small">
                            <Space direction="vertical" size={8} style={{ width: '100%' }}>
                              <Progress percent={detailProgress?.percent ?? 0} />
                              <Typography.Text type="secondary">
                                Создан {dayjs(selectedFranchisee.created_at).format('DD.MM.YYYY HH:mm')}
                              </Typography.Text>
                              <Typography.Text type="secondary">
                                Привязанных точек: {selectedFranchisee.points_count}
                              </Typography.Text>
                              {nextStage ? (
                                <Button
                                  type="primary"
                                  size="small"
                                  loading={stageMutation.isPending}
                                  onClick={() =>
                                    stageMutation.mutate({
                                      franchiseeId: selectedFranchiseeId!,
                                      nextStatus: nextStage,
                                    })
                                  }
                                >
                                  Следующая стадия: {STATUS_LABELS[nextStage]}
                                </Button>
                              ) : null}
                            </Space>
                          </Card>
                        </Col>
                      </Row>
                    </Space>
                  ),
                },
                {
                  key: 'tasks',
                  label: 'Чеклист',
                  children: detailTasksQuery.isLoading ? (
                    <Spin tip="Загрузка задач" />
                  ) : detailTasksQuery.isError ? (
                    <Alert
                      type="error"
                      message="Не удалось загрузить чеклист"
                      description={formatApiError(detailTasksQuery.error, 'Повторите запрос позже.')}
                      showIcon
                    />
                  ) : (
                    <Space direction="vertical" size={12} style={{ width: '100%' }}>
                      <Space style={{ justifyContent: 'space-between', width: '100%' }}>
                        <Typography.Text type="secondary">
                          {detailProgress ? `${detailProgress.done}/${detailProgress.total} выполнено (${detailProgress.percent}%)` : ''}
                        </Typography.Text>
                        <Button
                          size="small"
                          type="dashed"
                          icon={<PlusOutlined />}
                          onClick={() => {
                            createTaskForm.setFieldValue('stage', selectedFranchisee?.status ?? 'lead');
                            setIsCreateTaskOpen(true);
                          }}
                        >
                          Добавить задачу
                        </Button>
                      </Space>
                      <List
                        dataSource={detailTasks}
                        locale={{ emptyText: 'Нет задач' }}
                        renderItem={(task) => (
                          <List.Item
                            actions={[
                              <Select
                                key="status"
                                size="small"
                                value={task.status}
                                options={TASK_STATUS_OPTIONS}
                                loading={taskMutation.isPending}
                                style={{ width: 140 }}
                                onChange={(status: TaskStatus) =>
                                  taskMutation.mutate({
                                    franchiseeId: selectedFranchiseeId!,
                                    taskId: task.id,
                                    status,
                                  })
                                }
                              />,
                            ]}
                          >
                            <List.Item.Meta
                              title={task.title}
                              description={
                                <Space wrap>
                                  <Tag>{STATUS_LABELS[task.stage]}</Tag>
                                  <Tag color={task.status === 'done' ? 'green' : 'default'}>
                                    {TASK_STATUS_LABELS[task.status]}
                                  </Tag>
                                  {task.due_date ? (
                                    <Typography.Text type="secondary">
                                      Срок {dayjs(task.due_date).format('DD.MM.YYYY')}
                                    </Typography.Text>
                                  ) : null}
                                </Space>
                              }
                            />
                          </List.Item>
                        )}
                      />
                    </Space>
                  ),
                },
                {
                  key: 'history',
                  label: 'История',
                  children: (
                    <Space direction="vertical" size={16} style={{ width: '100%' }}>
                      <Form
                        form={noteForm}
                        layout="vertical"
                        onFinish={(values: { text: string }) =>
                          noteMutation.mutate({
                            franchiseeId: selectedFranchiseeId!,
                            text: values.text,
                          })
                        }
                      >
                        <Form.Item label="Заметка" name="text" rules={[{ required: true }]}>
                          <Input.TextArea rows={3} />
                        </Form.Item>
                        <Button type="primary" htmlType="submit" loading={noteMutation.isPending}>
                          Добавить заметку
                        </Button>
                      </Form>
                      {detailNotesQuery.isLoading ? (
                        <Spin tip="Загрузка истории" />
                      ) : detailNotesQuery.isError ? (
                        <Alert
                          type="error"
                          message="Не удалось загрузить историю"
                          description={formatApiError(detailNotesQuery.error, 'Повторите запрос позже.')}
                          showIcon
                        />
                      ) : (
                        <List
                          dataSource={[...detailNotes].sort((a, b) =>
                            dayjs(b.created_at).valueOf() - dayjs(a.created_at).valueOf(),
                          )}
                          locale={{ emptyText: 'История пока пуста' }}
                          renderItem={(item) => (
                            <List.Item>
                              <List.Item.Meta
                                title={item.author ?? 'Система'}
                                description={
                                  <Space direction="vertical" size={4}>
                                    <Typography.Text>{item.text}</Typography.Text>
                                    <Typography.Text type="secondary">
                                      {dayjs(item.created_at).format('DD.MM.YYYY HH:mm')}
                                    </Typography.Text>
                                  </Space>
                                }
                              />
                            </List.Item>
                          )}
                        />
                      )}
                    </Space>
                  ),
                },
                {
                  key: 'points',
                  label: 'Точки',
                  children: (
                    <Space direction="vertical" size={16} style={{ width: '100%' }}>
                      <Form
                        form={attachForm}
                        layout="vertical"
                        onFinish={(values: { point_id: string }) =>
                          attachPointMutation.mutate({
                            franchiseeId: selectedFranchiseeId!,
                            pointId: values.point_id,
                          })
                        }
                      >
                        <Space align="end" style={{ width: '100%' }} size={8}>
                          <Form.Item
                            name="point_id"
                            label="Привязать существующую точку"
                            rules={[{ required: true, message: 'Выберите точку' }]}
                            style={{ flex: 1, marginBottom: 0 }}
                          >
                            <Select
                              placeholder="Выберите точку"
                              options={attachOptions}
                              showSearch
                              optionFilterProp="label"
                              style={{ width: '100%' }}
                            />
                          </Form.Item>
                          <Form.Item style={{ marginBottom: 0 }}>
                            <Button
                              type="primary"
                              htmlType="submit"
                              loading={attachPointMutation.isPending}
                            >
                              Привязать
                            </Button>
                          </Form.Item>
                        </Space>
                      </Form>
                      <Form
                        form={createPointForm}
                        layout="vertical"
                        onFinish={(values: { name: string; address: string }) =>
                          createPointMutation.mutate({
                            franchiseeId: selectedFranchiseeId!,
                            name: values.name,
                            address: values.address,
                          })
                        }
                      >
                        <Form.Item
                          label="Название точки"
                          name="name"
                          rules={[{ required: true, message: 'Введите название точки' }]}
                        >
                          <Input placeholder="Например, Центр города" />
                        </Form.Item>
                        <Form.Item
                          label="Адрес"
                          name="address"
                          rules={[{ required: true, message: 'Введите адрес точки' }]}
                        >
                          <Input placeholder="Улица, дом, город" />
                        </Form.Item>
                        <Button
                          type="default"
                          htmlType="submit"
                          loading={createPointMutation.isPending}
                        >
                          Создать и привязать
                        </Button>
                      </Form>
                      {detailPointsQuery.isLoading ? (
                        <Spin tip="Загрузка точек" />
                      ) : detailPointsQuery.isError ? (
                        <Alert
                          type="error"
                          message="Не удалось загрузить точки франчайзи"
                          description={formatApiError(detailPointsQuery.error, 'Повторите запрос позже.')}
                          showIcon
                        />
                      ) : (
                        <List
                          dataSource={detailPoints}
                          locale={{ emptyText: 'Нет привязанных точек' }}
                          renderItem={(point) => (
                            <List.Item
                              actions={[
                                <Button
                                  key="detach"
                                  danger
                                  size="small"
                                  loading={detachPointMutation.isPending}
                                  onClick={() =>
                                    detachPointMutation.mutate({
                                      franchiseeId: selectedFranchiseeId!,
                                      pointId: point.id,
                                    })
                                  }
                                >
                                  Отвязать
                                </Button>,
                              ]}
                            >
                              <List.Item.Meta
                                title={point.name}
                                description={
                                  <Space direction="vertical" size={4}>
                                    <Typography.Text>{point.address}</Typography.Text>
                                    <Tag color={point.is_active ? 'green' : 'default'}>
                                      {point.is_active ? 'Активна' : 'Неактивна'}
                                    </Tag>
                                  </Space>
                                }
                              />
                            </List.Item>
                          )}
                        />
                      )}
                    </Space>
                  ),
                },
              ]}
            />
          </>
        )}
      </Drawer>
    </Space>
  );
}
