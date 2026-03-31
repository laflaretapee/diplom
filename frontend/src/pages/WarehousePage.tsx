import { useEffect, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import type { ColumnsType } from 'antd/es/table';
import axios from 'axios';
import {
  Alert,
  Button,
  Card,
  Col,
  ConfigProvider,
  Empty,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  theme as antdTheme,
} from 'antd';

import { apiClient } from '../api/client';
import { useAuthStore } from '../auth/store';
import type { Role } from '../auth/types';
import { ensureArray } from '../utils/ensureArray';

// ─── Types ────────────────────────────────────────────────────────────────────

interface PointRead {
  id: string;
  name: string;
}

interface IngredientRead {
  id: string;
  name: string;
  unit: string;
  min_stock_level: number | string;
  is_active: boolean;
}

interface StockRead {
  stock_item_id: string;
  point_id?: string;
  ingredient_id?: string;
  ingredient_name: string;
  quantity: number | string;
  min_stock_level: number | string;
  is_below_minimum: boolean;
}

interface MovementRead {
  id: string;
  stock_item_id?: string;
  ingredient_name: string;
  movement_type: string;
  quantity: number | string;
  reason: string | null;
  created_at: string;
  created_by_name: string | null;
}

interface SupplyResponse {
  stock_item_id: string;
  ingredient_id: string;
  new_quantity: number | string;
  movement_id: string;
}

interface MovementResponse {
  id: string;
  stock_item_id: string;
  movement_type: string;
  quantity: number | string;
  reason: string | null;
}

interface SupplyPayload {
  point_id: string;
  ingredient_id: string;
  quantity: number;
  supplier_name?: string;
  note?: string;
}

interface MovementPayload {
  point_id: string;
  stock_item_id: string;
  movement_type: 'adjustment';
  quantity: number;
  reason?: string;
}

type MutationNotice = {
  type: 'success' | 'error';
  text: string;
} | null;

// ─── Helpers ──────────────────────────────────────────────────────────────────

function authHeader(token: string | null): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function formatNumber(value: number | string | null | undefined): string {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return value === null || value === undefined ? '—' : String(value);
  }
  return numericValue.toLocaleString('ru-RU', {
    minimumFractionDigits: numericValue % 1 === 0 ? 0 : 2,
    maximumFractionDigits: 3,
  });
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail ?? error.response?.data?.message;
    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (typeof item === 'string') return item;
          if (item && typeof item === 'object' && 'msg' in item) {
            return String((item as { msg?: unknown }).msg ?? '');
          }
          return '';
        })
        .filter(Boolean)
        .join('; ');
    }
    if (error.message) {
      return error.message;
    }
    return 'Не удалось выполнить запрос';
  }
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return 'Не удалось выполнить запрос';
}

function hasWarehouseAccess(role: Role | null): boolean {
  return role === 'super_admin' || role === 'franchisee' || role === 'point_manager';
}

function movementMeta(type: string): { label: string; color: string } {
  switch (type) {
    case 'supply':
      return { label: 'Приход', color: 'green' };
    case 'adjustment':
      return { label: 'Корректировка', color: 'gold' };
    case 'in':
      return { label: 'Приход', color: 'blue' };
    case 'out':
      return { label: 'Расход', color: 'volcano' };
    default:
      return { label: type, color: 'default' };
  }
}

function formatMovementReason(record: MovementRead): string {
  const reason = record.reason?.trim();
  if (!reason) {
    return record.movement_type === 'in' ? 'Приход без комментария' : '—';
  }

  if (reason.startsWith('supply:')) {
    const [supplierPart, ...noteParts] = reason.split(';').map((part) => part.trim());
    const supplier = supplierPart.slice('supply:'.length).trim();
    const summary = supplier ? `Поставка от ${supplier}` : 'Поставка';
    const note = noteParts.filter(Boolean).join('; ');
    return note ? `${summary} · ${note}` : summary;
  }

  return reason;
}

// ─── API ──────────────────────────────────────────────────────────────────────

async function fetchPoints(token: string | null): Promise<PointRead[]> {
  const { data } = await apiClient.get<PointRead[]>('/v1/points', {
    headers: authHeader(token),
  });
  return data;
}

async function fetchIngredients(token: string | null): Promise<IngredientRead[]> {
  const { data } = await apiClient.get<IngredientRead[]>('/v1/warehouse/ingredients', {
    headers: authHeader(token),
    params: { is_active: true },
  });
  return data;
}

async function fetchStock(pointId: string, token: string | null): Promise<StockRead[]> {
  const { data } = await apiClient.get<StockRead[]>('/v1/warehouse/stock', {
    headers: authHeader(token),
    params: { point_id: pointId },
  });
  return data;
}

async function fetchMovements(pointId: string, token: string | null): Promise<MovementRead[]> {
  const { data } = await apiClient.get<MovementRead[]>('/v1/warehouse/stock/movements', {
    headers: authHeader(token),
    params: { point_id: pointId, limit: 50 },
  });
  return data;
}

async function supplyStock(payload: SupplyPayload, token: string | null): Promise<SupplyResponse> {
  const { data } = await apiClient.post<SupplyResponse>('/v1/warehouse/stock/supply', payload, {
    headers: authHeader(token),
  });
  return data;
}

async function adjustStock(payload: MovementPayload, token: string | null): Promise<MovementResponse> {
  const { data } = await apiClient.post<MovementResponse>('/v1/warehouse/stock/movements', payload, {
    headers: authHeader(token),
  });
  return data;
}

// ─── Page ─────────────────────────────────────────────────────────────────────

const pageBackground = 'linear-gradient(180deg, #0e0e0e 0%, #131313 55%, #0e0e0e 100%)';

export function WarehousePage() {
  const token = useAuthStore((state) => state.token);
  const role = useAuthStore((state) => state.role);
  const canAccess = hasWarehouseAccess(role);

  const [selectedPointId, setSelectedPointId] = useState<string>('');
  const [supplyForm] = Form.useForm();
  const [adjustForm] = Form.useForm();
  const [supplyNotice, setSupplyNotice] = useState<MutationNotice>(null);
  const [adjustNotice, setAdjustNotice] = useState<MutationNotice>(null);

  const {
    data: points = [],
    isLoading: pointsLoading,
    isError: pointsError,
    error: pointsQueryError,
    refetch: refetchPoints,
  } = useQuery({
    queryKey: ['warehouse', 'points', token],
    queryFn: () => fetchPoints(token),
    enabled: canAccess,
    retry: false,
    select: (data) => ensureArray<PointRead>(data),
  });

  const {
    data: ingredients = [],
    isLoading: ingredientsLoading,
    isError: ingredientsError,
    error: ingredientsQueryError,
    refetch: refetchIngredients,
  } = useQuery({
    queryKey: ['warehouse', 'ingredients', token],
    queryFn: () => fetchIngredients(token),
    enabled: canAccess,
    retry: false,
    select: (data) => ensureArray<IngredientRead>(data),
  });

  const {
    data: stock = [],
    isLoading: stockLoading,
    isError: stockError,
    error: stockQueryError,
    refetch: refetchStock,
  } = useQuery({
    queryKey: ['warehouse', 'stock', token, selectedPointId],
    queryFn: () => fetchStock(selectedPointId, token),
    enabled: canAccess && selectedPointId !== '',
    retry: false,
    select: (data) => ensureArray<StockRead>(data),
  });

  const {
    data: movements = [],
    isLoading: movementsLoading,
    isError: movementsError,
    error: movementsQueryError,
    refetch: refetchMovements,
  } = useQuery({
    queryKey: ['warehouse', 'movements', token, selectedPointId],
    queryFn: () => fetchMovements(selectedPointId, token),
    enabled: canAccess && selectedPointId !== '',
    retry: false,
    select: (data) => ensureArray<MovementRead>(data),
  });

  const supplyMutation = useMutation({
    mutationFn: (payload: SupplyPayload) => supplyStock(payload, token),
    onMutate: () => {
      setSupplyNotice(null);
    },
    onSuccess: async (data) => {
      setSupplyNotice({
        type: 'success',
        text: `Приход оформлен. Новый остаток: ${formatNumber(data.new_quantity)}.`,
      });
      supplyForm.resetFields();
      await Promise.all([refetchStock(), refetchMovements()]);
    },
    onError: (error) => {
      setSupplyNotice({
        type: 'error',
        text: formatError(error),
      });
    },
  });

  const adjustMutation = useMutation({
    mutationFn: (payload: MovementPayload) => adjustStock(payload, token),
    onMutate: () => {
      setAdjustNotice(null);
    },
    onSuccess: async (_data, variables) => {
      setAdjustNotice({
        type: 'success',
        text: `Корректировка сохранена. Остаток установлен на ${formatNumber(variables.quantity)}.`,
      });
      adjustForm.resetFields();
      await Promise.all([refetchStock(), refetchMovements()]);
    },
    onError: (error) => {
      setAdjustNotice({
        type: 'error',
        text: formatError(error),
      });
    },
  });

  useEffect(() => {
    if (!canAccess || points.length === 0) return;

    const pointExists = points.some((point) => point.id === selectedPointId);
    if (!selectedPointId) {
      setSelectedPointId(points[0].id);
      return;
    }
    if (!pointExists) {
      setSelectedPointId(points[0].id);
    }
  }, [canAccess, points, selectedPointId]);

  useEffect(() => {
    setSupplyNotice(null);
    setAdjustNotice(null);
    supplyForm.resetFields();
    adjustForm.resetFields();
  }, [adjustForm, selectedPointId, supplyForm]);

  const handleRefresh = async () => {
    await refetchPoints();
    await refetchIngredients();
    if (selectedPointId) {
      await Promise.all([refetchStock(), refetchMovements()]);
    }
  };

  const pointName = points.find((point) => point.id === selectedPointId)?.name ?? selectedPointId;

  const pointOptions = points.map((point) => ({ value: point.id, label: point.name }));
  const ingredientOptions = ingredients.map((ingredient) => ({
    value: ingredient.id,
    label: `${ingredient.name} · ${ingredient.unit}`,
  }));
  const stockOptions = stock.map((item) => ({
    value: item.stock_item_id,
    label: `${item.ingredient_name} · ${formatNumber(item.quantity)} / ${formatNumber(
      item.min_stock_level,
    )}`,
  }));
  const lowStockItems = stock.filter((item) => item.is_below_minimum);

  const ingredientColumns: ColumnsType<IngredientRead> = [
    { title: 'Название', dataIndex: 'name', key: 'name' },
    { title: 'Ед.', dataIndex: 'unit', key: 'unit', width: 90 },
    {
      title: 'Мин. остаток',
      dataIndex: 'min_stock_level',
      key: 'min_stock_level',
      width: 140,
      render: (value: number | string) => <span style={{ fontFamily: 'JetBrains Mono, monospace' }}>{formatNumber(value)}</span>,
    },
    {
      title: 'Активен',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 100,
      render: (value: boolean) => (value ? <Tag color="green">Да</Tag> : <Tag>Нет</Tag>),
    },
  ];

  const stockColumns: ColumnsType<StockRead> = [
    { title: 'Ингредиент', dataIndex: 'ingredient_name', key: 'ingredient_name' },
    {
      title: 'Остаток',
      dataIndex: 'quantity',
      key: 'quantity',
      width: 130,
      render: (value: number | string) => (
        <span style={{ fontFamily: 'JetBrains Mono, monospace' }}>{formatNumber(value)}</span>
      ),
    },
    {
      title: 'Мин. остаток',
      dataIndex: 'min_stock_level',
      key: 'min_stock_level',
      width: 140,
      render: (value: number | string) => (
        <span style={{ fontFamily: 'JetBrains Mono, monospace' }}>{formatNumber(value)}</span>
      ),
    },
    {
      title: 'Статус',
      dataIndex: 'is_below_minimum',
      key: 'is_below_minimum',
      width: 170,
      render: (value: boolean) =>
        value ? <Tag color="gold">Ниже минимума</Tag> : <Tag color="green">Норма</Tag>,
    },
  ];

  const movementColumns: ColumnsType<MovementRead> = [
    { title: 'Ингредиент', dataIndex: 'ingredient_name', key: 'ingredient_name' },
    {
      title: 'Тип',
      dataIndex: 'movement_type',
      key: 'movement_type',
      width: 150,
      render: (value: string) => {
        const meta = movementMeta(value);
        return <Tag color={meta.color}>{meta.label}</Tag>;
      },
    },
    {
      title: 'Кол-во',
      dataIndex: 'quantity',
      key: 'quantity',
      width: 110,
      render: (value: number | string) => (
        <span style={{ fontFamily: 'JetBrains Mono, monospace' }}>{formatNumber(value)}</span>
      ),
    },
    {
      title: 'Причина',
      dataIndex: 'reason',
      key: 'reason',
      render: (_value: string | null, record: MovementRead) => formatMovementReason(record),
    },
    {
      title: 'Когда',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: 'Кто',
      dataIndex: 'created_by_name',
      key: 'created_by_name',
      width: 160,
      render: (value: string | null) => value || '—',
    },
  ];

  const tableLocale = {
    emptyText: selectedPointId ? <Empty description="Нет данных" /> : <Empty description="Выберите точку" />,
  };

  const loadingAll = pointsLoading || ingredientsLoading || stockLoading || movementsLoading;
  const refreshLoading = loadingAll || supplyMutation.isPending || adjustMutation.isPending;

  return (
    <ConfigProvider
      theme={{
        algorithm: antdTheme.darkAlgorithm,
        token: {
          colorBgBase: '#0E0E0E',
          colorBgContainer: '#201F1F',
          colorBgElevated: '#2A2A2A',
          colorText: '#E5E2E1',
          colorTextSecondary: '#D3C4B3',
          colorBorder: '#4f4538',
          colorPrimary: '#E8B86D',
          colorPrimaryBg: '#2A2418',
          colorLink: '#FFD598',
          colorWarning: '#E8B86D',
          borderRadius: 10,
          fontFamily:
            'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
          fontFamilyCode: 'JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace',
        },
        components: {
          Card: {
            colorBgContainer: '#201F1F',
            headerBg: '#201F1F',
          },
          Table: {
            headerBg: '#2A2A2A',
            headerColor: '#D3C4B3',
            rowHoverBg: '#2A2A2A',
          },
          Input: {
            colorBgContainer: '#2A2A2A',
            colorBorder: '#4f4538',
            hoverBorderColor: '#FFD598',
            activeBorderColor: '#E8B86D',
          },
          Select: {
            colorBgContainer: '#2A2A2A',
            colorBorder: '#4f4538',
            optionSelectedBg: '#2A2418',
            optionActiveBg: '#2A2A2A',
          },
          Button: {
            defaultBg: '#2A2A2A',
            defaultColor: '#E5E2E1',
            defaultBorderColor: '#4f4538',
          },
        },
      }}
    >
      <div
        style={{
          minHeight: '100%',
          padding: 24,
          background: pageBackground,
          color: '#E5E2E1',
          fontFamily:
            'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        }}
      >
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Card
            style={{
              position: 'sticky',
              top: 16,
              zIndex: 5,
              background: 'rgba(14, 14, 14, 0.76)',
              borderColor: '#4f4538',
              backdropFilter: 'blur(18px)',
              boxShadow: '0 24px 48px rgba(0, 0, 0, 0.35)',
            }}
            styles={{ body: { padding: 16 } }}
          >
            <Row gutter={[16, 16]} align="middle">
              <Col xs={24} lg={10}>
                <Space direction="vertical" size={2} style={{ width: '100%' }}>
                  <Typography.Text style={{ color: '#D3C4B3', textTransform: 'uppercase', letterSpacing: 1.6, fontSize: 11 }}>
                    Склад
                  </Typography.Text>
                  <Space align="center" size={10} wrap>
                    <Typography.Title level={3} style={{ margin: 0, color: '#E5E2E1' }}>
                      Управление запасами
                    </Typography.Title>
                    <Tag
                      color="gold"
                      style={{
                        marginInlineEnd: 0,
                        borderColor: '#E8B86D',
                        color: '#FFD598',
                        background: 'rgba(232, 184, 109, 0.12)',
                        fontFamily: 'JetBrains Mono, monospace',
                      }}
                    >
                      {selectedPointId ? pointName : 'ТОЧКА'}
                    </Tag>
                  </Space>
                </Space>
              </Col>

              <Col xs={24} lg={10}>
                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Typography.Text style={{ color: '#D3C4B3', fontSize: 12 }}>
                    Выбор точки
                  </Typography.Text>
                  <Select
                    placeholder="Выберите точку"
                    style={{ width: '100%' }}
                    options={pointOptions}
                    value={selectedPointId || undefined}
                    onChange={(value: string) => setSelectedPointId(value)}
                    loading={pointsLoading}
                    notFoundContent={pointsError ? 'Ошибка загрузки' : 'Нет точек'}
                    optionFilterProp="label"
                    showSearch
                  />
                </Space>
              </Col>

              <Col xs={24} lg={4}>
                <Button
                  block
                  onClick={() => {
                    void handleRefresh();
                  }}
                  loading={refreshLoading}
                  style={{
                    height: 42,
                    border: '1px solid #4f4538',
                    background: 'linear-gradient(135deg, rgba(42, 42, 42, 0.95) 0%, rgba(32, 31, 31, 0.95) 100%)',
                    color: '#E5E2E1',
                    boxShadow: '0 8px 24px rgba(0, 0, 0, 0.25)',
                  }}
                >
                  Обновить
                </Button>
              </Col>
            </Row>

            {pointsError ? (
              <Alert
                type="error"
                message="Не удалось загрузить точки"
                description={formatError(pointsQueryError)}
                showIcon
                style={{ marginTop: 16 }}
              />
            ) : null}
          </Card>

          <Row gutter={[16, 16]}>
            <Col xs={24} xl={12}>
              <Card
                title={<span style={{ color: '#E5E2E1' }}>Приход</span>}
                style={{ borderColor: '#4f4538' }}
                styles={{ body: { paddingTop: 16 } }}
              >
                {supplyNotice ? (
                  <Alert
                    type={supplyNotice.type}
                    message={supplyNotice.type === 'success' ? 'Приход сохранён' : 'Не удалось оформить приход'}
                    description={supplyNotice.text}
                    showIcon
                    style={{ marginBottom: 12 }}
                  />
                ) : null}
                <Form
                  form={supplyForm}
                  layout="vertical"
                  onFinish={(values: { ingredient_id: string; quantity: number; supplier_name?: string; note?: string }) => {
                    if (!selectedPointId) return;
                    void supplyMutation.mutateAsync({
                      point_id: selectedPointId,
                      ingredient_id: values.ingredient_id,
                      quantity: values.quantity,
                      supplier_name: values.supplier_name?.trim() || undefined,
                      note: values.note?.trim() || undefined,
                    });
                  }}
                >
                  <Row gutter={12}>
                    <Col xs={24} md={12}>
                      <Form.Item
                        name="ingredient_id"
                        label="Ингредиент"
                        rules={[{ required: true, message: 'Выберите ингредиент' }]}
                      >
                        <Select
                          placeholder="Ингредиент"
                          options={ingredientOptions}
                          loading={ingredientsLoading}
                          notFoundContent={ingredientsError ? 'Ошибка загрузки' : 'Нет активных ингредиентов'}
                          showSearch
                          optionFilterProp="label"
                        />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={12}>
                      <Form.Item
                        name="quantity"
                        label="Количество"
                        rules={[{ required: true, message: 'Укажите количество' }]}
                      >
                        <InputNumber min={0.001} precision={3} step={0.1} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={12}>
                      <Form.Item name="supplier_name" label="Поставщик">
                        <Input placeholder="Необязательно" />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={12}>
                      <Form.Item name="note" label="Комментарий">
                        <Input placeholder="Необязательно" />
                      </Form.Item>
                    </Col>
                  </Row>

                  {supplyMutation.isError ? (
                    <Alert
                      type="error"
                      message="Не удалось оформить приход"
                      description={formatError(supplyMutation.error)}
                      showIcon
                      style={{ marginBottom: 12 }}
                    />
                  ) : null}

                  <Button
                    htmlType="submit"
                    loading={supplyMutation.isPending}
                    disabled={!selectedPointId}
                    style={{
                      height: 42,
                      border: 'none',
                      background: 'linear-gradient(135deg, #FFD598 0%, #E8B86D 100%)',
                      color: '#281800',
                      fontWeight: 800,
                      boxShadow: '0 14px 30px rgba(232, 184, 109, 0.20)',
                    }}
                  >
                    Сохранить приход
                  </Button>
                </Form>
              </Card>
            </Col>

            <Col xs={24} xl={12}>
              <Card
                title={<span style={{ color: '#E5E2E1' }}>Корректировка остатка</span>}
                style={{ borderColor: '#4f4538' }}
                styles={{ body: { paddingTop: 16 } }}
              >
                {adjustNotice ? (
                  <Alert
                    type={adjustNotice.type}
                    message={adjustNotice.type === 'success' ? 'Корректировка сохранена' : 'Не удалось сохранить корректировку'}
                    description={adjustNotice.text}
                    showIcon
                    style={{ marginBottom: 12 }}
                  />
                ) : null}
                <Form
                  form={adjustForm}
                  layout="vertical"
                  onFinish={(values: { stock_item_id: string; quantity: number; reason?: string }) => {
                    void adjustMutation.mutateAsync({
                      point_id: selectedPointId,
                      stock_item_id: values.stock_item_id,
                      movement_type: 'adjustment',
                      quantity: values.quantity,
                      reason: values.reason?.trim() || undefined,
                    });
                  }}
                >
                  <Row gutter={12}>
                    <Col xs={24}>
                      <Form.Item
                        name="stock_item_id"
                        label="Позиция склада"
                        rules={[{ required: true, message: 'Выберите позицию склада' }]}
                      >
                        <Select
                          placeholder="Позиция склада"
                          options={stockOptions}
                          loading={stockLoading}
                          notFoundContent={stockError ? 'Ошибка загрузки' : 'Нет остатков'}
                          showSearch
                          optionFilterProp="label"
                        />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={12}>
                      <Form.Item
                        name="quantity"
                        label="Новый остаток"
                        rules={[{ required: true, message: 'Укажите новый остаток' }]}
                      >
                        <InputNumber min={0} precision={3} step={0.1} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={12}>
                      <Form.Item name="reason" label="Причина">
                        <Input placeholder="Обязательно для контроля" />
                      </Form.Item>
                    </Col>
                  </Row>

                  {adjustMutation.isError ? (
                    <Alert
                      type="error"
                      message="Не удалось сохранить корректировку"
                      description={formatError(adjustMutation.error)}
                      showIcon
                      style={{ marginBottom: 12 }}
                    />
                  ) : null}

                  <Button
                    htmlType="submit"
                    loading={adjustMutation.isPending}
                    disabled={!selectedPointId}
                    style={{
                      height: 42,
                      border: 'none',
                      background: 'linear-gradient(135deg, #FFD598 0%, #E8B86D 100%)',
                      color: '#281800',
                      fontWeight: 800,
                      boxShadow: '0 14px 30px rgba(232, 184, 109, 0.20)',
                    }}
                  >
                    Сохранить корректировку
                  </Button>
                </Form>
              </Card>
            </Col>
          </Row>

          <Row gutter={[16, 16]}>
            <Col xs={24} xl={10}>
              <Card
                title={<span style={{ color: '#E5E2E1' }}>Каталог ингредиентов</span>}
                style={{ borderColor: '#4f4538' }}
                styles={{ body: { paddingTop: 12 } }}
              >
                {ingredientsError ? (
                  <Alert
                    type="error"
                    message="Не удалось загрузить каталог"
                    description={formatError(ingredientsQueryError)}
                    showIcon
                  />
                ) : (
                  <Spin spinning={ingredientsLoading}>
                    <Table<IngredientRead>
                      rowKey="id"
                      columns={ingredientColumns}
                      dataSource={ingredients}
                      pagination={{ pageSize: 8, size: 'small' }}
                      scroll={{ x: true }}
                      size="small"
                      locale={{
                        emptyText: <Empty description="Нет активных ингредиентов" />,
                      }}
                    />
                  </Spin>
                )}
              </Card>
            </Col>

            <Col xs={24} xl={14}>
              <Card
                title={<span style={{ color: '#E5E2E1' }}>Остатки по точке</span>}
                style={{ borderColor: '#4f4538' }}
                styles={{ body: { paddingTop: 12 } }}
              >
                {lowStockItems.length > 0 ? (
                  <Alert
                    type="warning"
                    message={`Ниже минимума: ${lowStockItems.length} позиций`}
                    description={lowStockItems
                      .map((item) => `${item.ingredient_name} — ${formatNumber(item.quantity)} из ${formatNumber(item.min_stock_level)}`)
                      .join('; ')}
                    showIcon
                    style={{ marginBottom: 12 }}
                  />
                ) : null}
                {stockError ? (
                  <Alert
                    type="error"
                    message="Не удалось загрузить остатки"
                    description={formatError(stockQueryError)}
                    showIcon
                  />
                ) : (
                  <Spin spinning={stockLoading}>
                    <Table<StockRead>
                      rowKey="stock_item_id"
                      columns={stockColumns}
                      dataSource={stock}
                      pagination={{ pageSize: 8, size: 'small' }}
                      scroll={{ x: true }}
                      size="small"
                      locale={tableLocale}
                      onRow={(record) => ({
                        style: record.is_below_minimum
                          ? { background: 'rgba(232, 184, 109, 0.08)' }
                          : undefined,
                      })}
                    />
                  </Spin>
                )}
              </Card>
            </Col>
          </Row>

          <Card
            title={<span style={{ color: '#E5E2E1' }}>История движений</span>}
            style={{ borderColor: '#4f4538' }}
            styles={{ body: { paddingTop: 12 } }}
          >
            {movementsError ? (
              <Alert
                type="error"
                message="Не удалось загрузить историю движений"
                description={formatError(movementsQueryError)}
                showIcon
              />
            ) : (
              <Spin spinning={movementsLoading}>
                <Table<MovementRead>
                  rowKey="id"
                  columns={movementColumns}
                  dataSource={movements}
                  pagination={{ pageSize: 10, size: 'small' }}
                  scroll={{ x: true }}
                  size="small"
                  locale={tableLocale}
                />
              </Spin>
            )}
          </Card>
        </Space>
      </div>
    </ConfigProvider>
  );
}
