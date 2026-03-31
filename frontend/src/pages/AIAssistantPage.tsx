import { useEffect, useMemo, useRef, useState } from 'react';
import {
  DatabaseOutlined,
  FileTextOutlined,
  HistoryOutlined,
  LoadingOutlined,
  RobotOutlined,
  SearchOutlined,
  SendOutlined,
  ThunderboltOutlined,
  UserOutlined,
  WarningOutlined,
  ExperimentOutlined,
  RiseOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Button, Card, Empty, Input, Select, Space, Spin, Tag, Typography } from 'antd';
import type { InputRef } from 'antd';

import { apiClient } from '../api/client';
import { roleMeta } from '../auth/roleMeta';
import { useAuthStore } from '../auth/store';
import type { Role } from '../auth/types';
import { ensureArray } from '../utils/ensureArray';

type AssistantEvidence = {
  label: string;
  value: string;
  detail?: string | null;
};

type AssistantChatResponse = {
  answer: string;
  provider: string;
  used_fallback: boolean;
  evidence: AssistantEvidence[];
  suggestions: string[];
  context_scope: string;
};

type AssistantChatRequest = {
  question: string;
  pointId: string | null;
};

type TurnStatus = 'loading' | 'done' | 'error';

type ChatTurn = {
  turnId: string;
  question: string;
  askedAt: number;
  status: TurnStatus;
  response?: AssistantChatResponse;
  error?: string;
};

type PointRead = {
  id: string;
  name: string;
};

const ALLOWED_ROLES: Role[] = ['super_admin', 'franchisee'];
const ALL_POINTS_VALUE = '__all__';
const PROVIDER_LABELS: Record<string, string> = {
  disabled: 'ИИ отключён',
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  ollama: 'Ollama',
  qwen_api: 'Qwen API',
};

function isSystemLabel(value: string): boolean {
  return /^[a-z0-9_:-]+$/i.test(value);
}

function authHeader(token: string | null): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function createTurnId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatPointLabel(name: string): string {
  return name.trim() || 'Неизвестная точка';
}

function formatProviderLabel(provider: string | null | undefined): string {
  const value = provider?.trim();
  if (!value) {
    return 'Провайдер не выбран';
  }

  if (PROVIDER_LABELS[value]) {
    return PROVIDER_LABELS[value];
  }

  if (value.startsWith('qwen_api:')) {
    return `Qwen API · ${value.slice('qwen_api:'.length)}`;
  }

  if (value.startsWith('ollama:')) {
    return `Ollama · ${value.slice('ollama:'.length)}`;
  }

  if (isSystemLabel(value)) {
    return 'Пользовательский провайдер';
  }

  return value;
}

function formatContextScopeLabel(scope: string | null | undefined): string {
  const value = scope?.trim();
  if (!value) {
    return 'Контекст не определён';
  }

  if (value === 'network') {
    return 'Вся сеть';
  }

  if (value === 'assigned_points') {
    return 'Назначенные точки';
  }

  if (value === 'all_points') {
    return 'Все точки';
  }

  if (isSystemLabel(value)) {
    return 'Пользовательский контекст';
  }

  return value;
}

function getErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null) {
    const maybeError = error as { response?: { data?: { message?: unknown } }; message?: unknown };
    const message = maybeError.response?.data?.message ?? maybeError.message;
    if (typeof message === 'string' && message.trim()) {
      return message;
    }
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return 'Не удалось загрузить ответ ассистента.';
}

function getActivePointLabel(pointId: string | null, points: PointRead[]): string {
  const safePoints = ensureArray<PointRead>(points);
  if (!pointId) {
    return 'Все точки';
  }

  return safePoints.find((point) => point.id === pointId)?.name ?? 'Выбранная точка';
}

function getAssistantStatus({
  pointsLoading,
  pointsError,
  latestDoneTurn,
}: {
  pointsLoading: boolean;
  pointsError: boolean;
  latestDoneTurn: ChatTurn | null;
}): { tone: 'neutral' | 'accent' | 'warning' | 'danger'; label: string; description: string } {
  if (pointsLoading) {
    return {
      tone: 'warning',
      label: 'ЗАГРУЗКА КОНТЕКСТА',
      description: 'Загружаем список точек и подготавливаем контекст ответа.',
    };
  }

  if (pointsError) {
    return {
      tone: 'danger',
      label: 'КОНТЕКСТ ОГРАНИЧЕН',
      description: 'Список точек недоступен, но ассистент может отвечать в общем контуре.',
    };
  }

  if (latestDoneTurn?.response?.used_fallback) {
    return {
      tone: 'warning',
      label: 'РЕЗЕРВНЫЙ РЕЖИМ',
      description: 'Последний ответ был собран через резервного провайдера.',
    };
  }

  if (latestDoneTurn?.response?.provider) {
    return {
      tone: 'accent',
      label: 'КОНТЕКСТ ГОТОВ',
      description: `Последний ответ пришёл от ${formatProviderLabel(latestDoneTurn.response.provider)}.`,
    };
  }

  return {
    tone: 'neutral',
    label: 'КОНТЕКСТ ГОТОВ',
    description: 'Выберите точку и задайте вопрос.',
  };
}

function buildQuickInsights(scopeLabel: string): { title: string; question: string; icon: JSX.Element }[] {
  return [
    {
      title: 'Аномалии недели',
      question: `Какие аномалии требуют внимания в контуре «${scopeLabel}» на этой неделе?`,
      icon: <WarningOutlined />,
    },
    {
      title: 'Динамика выручки',
      question: `Почему выручка в контуре «${scopeLabel}» изменилась за последние 7 дней?`,
      icon: <RiseOutlined />,
    },
    {
      title: 'Операционный риск',
      question: `Какие сигналы прямо сейчас указывают на операционные проблемы в контуре «${scopeLabel}»?`,
      icon: <ExperimentOutlined />,
    },
    {
      title: 'Краткая сводка',
      question: `Сделай краткую сводку по текущим показателям для контура «${scopeLabel}».`,
      icon: <DatabaseOutlined />,
    },
  ];
}

const SAVED_SCENARIOS = [
  {
    title: 'Ежемесячная сводка сети',
    question: 'Подготовь ежемесячную ИИ-сводку по выручке, аномалиям и рекомендуемым действиям.',
  },
  {
    title: 'Проверка эффекта промо',
    question: 'Оцени, улучшили ли последние промо конверсию или только перераспределили спрос.',
  },
  {
    title: 'Проверка здоровья точки',
    question: 'Определи точку с наибольшим риском и объясни, что требует немедленного внимания.',
  },
  {
    title: 'Аудит резервного режима',
    question: 'Объясни, где ассистент переходит в резервный режим и каким данным он при этом доверяет.',
  },
];

function PageSectionLabel({ children }: { children: string }) {
  return (
    <Typography.Text
      style={{
        color: '#E8B86D',
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: '0.22em',
        textTransform: 'uppercase',
      }}
    >
      {children}
    </Typography.Text>
  );
}

function MonoBadge({
  children,
  tone = 'neutral',
}: {
  children: string;
  tone?: 'neutral' | 'accent' | 'warning' | 'danger';
}) {
  const tones: Record<typeof tone, { background: string; border: string; color: string }> = {
    neutral: { background: '#2A2A2A', border: '#4F4538', color: '#D3C4B3' },
    accent: { background: '#2A2418', border: '#8A6A2A', color: '#FFD598' },
    warning: { background: '#32261B', border: '#8A6A2A', color: '#E8B86D' },
    danger: { background: '#331E1E', border: '#7E3434', color: '#FFB4AB' },
  };

  const style = tones[tone];

  return (
    <Tag
      style={{
        marginInlineEnd: 0,
        background: style.background,
        borderColor: style.border,
        color: style.color,
        fontFamily: '"JetBrains Mono", monospace',
        fontSize: 10,
        lineHeight: '16px',
        borderRadius: 999,
        paddingInline: 10,
      }}
    >
      {children}
    </Tag>
  );
}

function PromptButton({
  title,
  subtitle,
  icon,
  onClick,
}: {
  title: string;
  subtitle: string;
  icon: JSX.Element;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        width: '100%',
        padding: 14,
        background: '#201F1F',
        border: '1px solid #2A2A2A',
        borderRadius: 8,
        color: '#E5E2E1',
        textAlign: 'left',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: 10,
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1, minWidth: 0 }}>
        <Typography.Text strong style={{ color: '#E5E2E1', fontSize: 13, display: 'block' }}>
          {title}
        </Typography.Text>
        <Typography.Text style={{ color: '#BFB6A8', fontSize: 11, lineHeight: 1.4, display: 'block', whiteSpace: 'normal', wordBreak: 'break-word' }}>
          {subtitle}
        </Typography.Text>
      </div>
      <span style={{ color: '#E8B86D', fontSize: 16, lineHeight: 1, flexShrink: 0 }}>{icon}</span>
    </button>
  );
}

function AccessDeniedCard({ roleLabel }: { roleLabel: string }) {
  return (
    <div
      style={{
        minHeight: 'calc(100vh - 112px)',
        display: 'grid',
        placeItems: 'center',
        padding: 24,
      }}
    >
      <Card
        bordered={false}
        style={{
          width: '100%',
          maxWidth: 620,
          background: '#131313',
          border: '1px solid #2A2A2A',
          boxShadow: '0 24px 70px rgba(0, 0, 0, 0.30)',
        }}
      >
        <Space direction="vertical" size={18} style={{ width: '100%' }}>
          <Space align="center" size={12}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 12,
                display: 'grid',
                placeItems: 'center',
                background: '#2A2418',
                color: '#FFD598',
                border: '1px solid #4F4538',
              }}
            >
              <CloseCircleOutlined />
            </div>
            <div>
              <Typography.Title level={4} style={{ color: '#E5E2E1', margin: 0 }}>
                Доступ закрыт
              </Typography.Title>
              <Typography.Text style={{ color: '#BFB6A8' }}>
                Этот ассистент доступен только суперадминистратору и франчайзи.
              </Typography.Text>
            </div>
          </Space>
          <Typography.Paragraph style={{ color: '#D3C4B3', marginBottom: 0 }}>
            Текущая роль: <strong>{roleLabel}</strong>. Для этой роли страница остаётся
            недоступной, чтобы сохранить демо-контур аналитического ассистента в рамках
            согласованного сценария.
          </Typography.Paragraph>
          <MonoBadge tone="warning">БЛОК ДОСТУПА</MonoBadge>
        </Space>
      </Card>
    </div>
  );
}

function UserBubble({ question, askedAt }: { question: string; askedAt: number }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
      <div style={{ maxWidth: 'min(760px, 88%)', display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
        <div
          style={{
            background: '#201F1F',
            border: '1px solid #2A2A2A',
            borderRadius: 18,
            borderTopRightRadius: 4,
            padding: '14px 16px',
            boxShadow: '0 12px 30px rgba(0, 0, 0, 0.18)',
          }}
        >
          <Typography.Paragraph
            style={{
              marginBottom: 0,
              color: '#E5E2E1',
              whiteSpace: 'pre-wrap',
              fontSize: 14,
              lineHeight: 1.65,
            }}
          >
            {question}
          </Typography.Paragraph>
        </div>
        <Typography.Text style={{ color: '#9B8F7F', fontFamily: '"JetBrains Mono", monospace', fontSize: 10 }}>
          {formatTime(askedAt)} • Вы
        </Typography.Text>
      </div>
    </div>
  );
}

function EvidenceGrid({ items }: { items: AssistantEvidence[] }) {
  if (!items.length) {
    return null;
  }

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 10,
      }}
    >
      {items.map((item) => (
        <div
          key={`${item.label}-${item.value}`}
          style={{
            background: '#131313',
            border: '1px solid #2A2A2A',
            borderRadius: 14,
            padding: 14,
          }}
        >
          <Typography.Text style={{ color: '#9B8F7F', fontSize: 10, letterSpacing: '0.16em', textTransform: 'uppercase' }}>
            {item.label}
          </Typography.Text>
          <Typography.Paragraph
            style={{
              marginBottom: item.detail ? 8 : 0,
              marginTop: 8,
              color: '#FFD598',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: 13,
              lineHeight: 1.5,
            }}
          >
            {item.value}
          </Typography.Paragraph>
          {item.detail ? (
            <Typography.Text style={{ color: '#D3C4B3', fontSize: 12, lineHeight: 1.5 }}>
              {item.detail}
            </Typography.Text>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function SuggestionsRow({ suggestions, onPick }: { suggestions: string[]; onPick: (value: string) => void }) {
  if (!suggestions.length) {
    return null;
  }

  return (
    <Space wrap size={8}>
      {suggestions.map((suggestion) => (
        <Button
          key={suggestion}
          size="small"
          onClick={() => onPick(suggestion)}
          style={{
            borderRadius: 999,
            background: '#2A2A2A',
            borderColor: '#4F4538',
            color: '#E5E2E1',
          }}
        >
          {suggestion}
        </Button>
      ))}
    </Space>
  );
}

function AssistantBubble({
  turn,
  onSuggestionPick,
}: {
  turn: ChatTurn;
  onSuggestionPick: (value: string) => void;
}) {
  const response = turn.response;

  if (turn.status === 'loading') {
    return (
      <div style={{ display: 'flex', gap: 12 }}>
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: 12,
            display: 'grid',
            placeItems: 'center',
            background: 'linear-gradient(135deg, #2A2418 0%, #201F1F 100%)',
            border: '1px solid #4F4538',
            color: '#E8B86D',
            flexShrink: 0,
          }}
        >
          <Spin indicator={<LoadingOutlined style={{ color: '#E8B86D' }} spin />} />
        </div>
        <div style={{ flex: 1 }}>
          <div
            style={{
              maxWidth: 'min(900px, 92%)',
              background: '#201F1F',
              border: '1px solid #2A2A2A',
              borderRadius: 18,
              borderTopLeftRadius: 4,
              padding: '14px 16px',
            }}
          >
            <Space direction="vertical" size={10} style={{ width: '100%' }}>
              <Space size={8} wrap>
                <MonoBadge tone="accent">АНАЛИЗ</MonoBadge>
                <MonoBadge>ОЖИДАЕМ МОДЕЛЬ</MonoBadge>
              </Space>
              <Typography.Text style={{ color: '#D3C4B3' }}>
                Ассистент собирает контекст и формирует ответ.
              </Typography.Text>
            </Space>
          </div>
        </div>
      </div>
    );
  }

  if (turn.status === 'error') {
    return (
      <div style={{ display: 'flex', gap: 12 }}>
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: 12,
            display: 'grid',
            placeItems: 'center',
            background: '#331E1E',
            border: '1px solid #7E3434',
            color: '#FFB4AB',
            flexShrink: 0,
          }}
        >
          <WarningOutlined />
        </div>
        <div
          style={{
            maxWidth: 'min(900px, 92%)',
            background: '#201F1F',
            border: '1px solid #4A2A2A',
            borderRadius: 18,
            borderTopLeftRadius: 4,
            padding: '14px 16px',
          }}
        >
          <Space direction="vertical" size={10} style={{ width: '100%' }}>
            <Space size={8} wrap>
              <MonoBadge tone="danger">ОШИБКА АССИСТЕНТА</MonoBadge>
              <MonoBadge tone="neutral">ВОПРОС СОХРАНЕН В ИСТОРИИ</MonoBadge>
            </Space>
            <Typography.Text style={{ color: '#FFB4AB' }}>{turn.error}</Typography.Text>
          </Space>
        </div>
      </div>
    );
  }

  if (!response) {
    return null;
  }

  return (
    <div style={{ display: 'flex', gap: 12 }}>
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: 12,
          display: 'grid',
          placeItems: 'center',
          background: 'linear-gradient(135deg, #FFD598 0%, #E8B86D 100%)',
          color: '#281800',
          border: '1px solid rgba(232, 184, 109, 0.30)',
          boxShadow: '0 12px 28px rgba(232, 184, 109, 0.16)',
          flexShrink: 0,
        }}
      >
        <RobotOutlined />
      </div>
      <div style={{ flex: 1, maxWidth: 'min(980px, 92%)' }}>
        <div
          style={{
            background: '#201F1F',
            border: '1px solid #2A2A2A',
            borderRadius: 18,
            borderTopLeftRadius: 4,
            padding: 16,
            boxShadow: '0 18px 40px rgba(0, 0, 0, 0.18)',
          }}
        >
          <Space direction="vertical" size={14} style={{ width: '100%' }}>
            <Space size={8} wrap>
              <MonoBadge tone="accent">{formatProviderLabel(response.provider)}</MonoBadge>
              {response.used_fallback ? <MonoBadge tone="warning">РЕЗЕРВНЫЙ ОТВЕТ</MonoBadge> : null}
              <MonoBadge tone="neutral">{formatContextScopeLabel(response.context_scope)}</MonoBadge>
            </Space>
            <Typography.Paragraph
              style={{
                marginBottom: 0,
                color: '#E5E2E1',
                whiteSpace: 'pre-wrap',
                fontSize: 14,
                lineHeight: 1.7,
              }}
            >
              {response.answer}
            </Typography.Paragraph>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 12,
                flexWrap: 'wrap',
              }}
            >
              <Typography.Text style={{ color: '#9B8F7F', fontSize: 11, letterSpacing: '0.16em', textTransform: 'uppercase' }}>
                Основания
              </Typography.Text>
            </div>
            <EvidenceGrid items={response.evidence} />
            <div
              style={{
                padding: 14,
                borderRadius: 14,
                background: '#2A2418',
                border: '1px solid #4F4538',
              }}
            >
              <Typography.Text
                style={{
                  display: 'block',
                  color: '#E8B86D',
                  fontSize: 10,
                  letterSpacing: '0.18em',
                  textTransform: 'uppercase',
                  marginBottom: 10,
                }}
              >
                Подсказки
              </Typography.Text>
              <SuggestionsRow suggestions={response.suggestions} onPick={onSuggestionPick} />
            </div>
          </Space>
        </div>
      </div>
    </div>
  );
}

function EmptyState({
  onPickPrompt,
  scopeLabel,
  statusLabel,
  statusDescription,
  statusTone,
}: {
  onPickPrompt: (question: string) => void;
  scopeLabel: string;
  statusLabel: string;
  statusDescription: string;
  statusTone: 'neutral' | 'accent' | 'warning' | 'danger';
}) {
  return (
    <Card
      bordered={false}
      style={{
        background: '#131313',
        border: '1px solid #2A2A2A',
        boxShadow: '0 18px 40px rgba(0, 0, 0, 0.20)',
      }}
    >
      <Space direction="vertical" size={18} style={{ width: '100%' }}>
        <Space align="center" size={12}>
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 14,
              display: 'grid',
              placeItems: 'center',
              background: '#2A2418',
              color: '#FFD598',
              border: '1px solid #4F4538',
            }}
          >
            <SearchOutlined />
          </div>
          <div>
            <Typography.Title level={4} style={{ color: '#E5E2E1', margin: 0 }}>
              Спросите ассистента
            </Typography.Title>
            <Typography.Text style={{ color: '#BFB6A8' }}>
              Контекст: <strong>{scopeLabel}</strong>. Используйте готовые сценарии слева или
              задайте свой аналитический вопрос.
            </Typography.Text>
          </div>
        </Space>
        <div
          style={{
            padding: 12,
            borderRadius: 14,
            border: '1px solid #2A2A2A',
            background: '#1A1A1A',
          }}
        >
          <Space align="center" size={8} wrap>
            <MonoBadge tone={statusTone}>{statusLabel}</MonoBadge>
            <Typography.Text style={{ color: '#BFB6A8', fontSize: 12, lineHeight: 1.5 }}>
              {statusDescription}
            </Typography.Text>
          </Space>
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: 12,
          }}
        >
          {[
            'Почему выручка изменилась на этой неделе?',
            'Какие аномалии требуют срочного внимания?',
            'Суммируйте операционный риск для этого контура.',
            'Какому доказательству стоит доверять больше всего?',
          ].map((question) => (
            <Button
              key={question}
              onClick={() => onPickPrompt(question)}
              style={{
                height: 'auto',
                minHeight: 64,
                padding: 14,
                textAlign: 'left',
                background: '#201F1F',
                borderColor: '#2A2A2A',
                color: '#E5E2E1',
              }}
            >
              {question}
            </Button>
          ))}
        </div>
      </Space>
    </Card>
  );
}

export function AIAssistantPage() {
  const token = useAuthStore((state) => state.token);
  const role = useAuthStore((state) => state.role);
  const isAllowed = role ? ALLOWED_ROLES.includes(role) : false;
  const inputRef = useRef<InputRef>(null);
  const scrollEndRef = useRef<HTMLDivElement | null>(null);
  const [draft, setDraft] = useState('');
  const [pointFilter, setPointFilter] = useState<string>(ALL_POINTS_VALUE);
  const [turns, setTurns] = useState<ChatTurn[]>([]);

  const pointsQuery = useQuery({
    queryKey: ['assistant-points', token],
    queryFn: async () => {
      const { data } = await apiClient.get<PointRead[]>('/v1/points', {
        headers: authHeader(token),
      });

      return data;
    },
    enabled: isAllowed && Boolean(token),
    select: (data) => ensureArray<PointRead>(data),
  });

  const chatMutation = useMutation({
    mutationFn: async ({ question, pointId }: AssistantChatRequest) => {
      const { data } = await apiClient.post<AssistantChatResponse>(
        '/v1/analytics/assistant/chat',
        {
          question,
          point_id: pointId,
        },
        {
          headers: authHeader(token),
        },
      );

      return data;
    },
  });

  const selectedPointId = pointFilter === ALL_POINTS_VALUE ? null : pointFilter;
  const assistantPoints = ensureArray<PointRead>(pointsQuery.data);
  const selectedPointLabel = getActivePointLabel(selectedPointId, assistantPoints);
  const quickInsights = useMemo(() => buildQuickInsights(selectedPointLabel), [selectedPointLabel]);
  const latestDoneTurn = useMemo(
    () => [...turns].reverse().find((turn) => turn.status === 'done' && turn.response),
    [turns],
  );
  const assistantStatus = getAssistantStatus({
    pointsLoading: pointsQuery.isLoading,
    pointsError: pointsQuery.isError,
    latestDoneTurn: latestDoneTurn ?? null,
  });

  useEffect(() => {
    scrollEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [turns.length, chatMutation.isPending]);

  const handlePrefill = (question: string) => {
    setDraft(question);
    inputRef.current?.focus();
  };

  const handleSubmit = async () => {
    const question = draft.trim();
    if (!question || chatMutation.isPending || !isAllowed) {
      return;
    }

    const turnId = createTurnId();
    const askedAt = Date.now();

    setTurns((current) => [
      ...current,
      {
        turnId,
        question,
        askedAt,
        status: 'loading',
      },
    ]);
    setDraft('');

    try {
      const response = await chatMutation.mutateAsync({
        question,
        pointId: selectedPointId,
      });

      setTurns((current) =>
        current.map((turn) =>
          turn.turnId === turnId
            ? {
                ...turn,
                status: 'done',
                response,
              }
            : turn,
        ),
      );
    } catch (error) {
      setTurns((current) =>
        current.map((turn) =>
          turn.turnId === turnId
            ? {
                ...turn,
                status: 'error',
                error: getErrorMessage(error),
              }
            : turn,
        ),
      );
    }
  };

  if (!role || !isAllowed) {
    return <AccessDeniedCard roleLabel={role ? roleMeta[role].label : 'Роль не определена'} />;
  }

  const pointOptions = [
    {
      value: ALL_POINTS_VALUE,
      label: 'Все точки',
    },
    ...assistantPoints.map((point) => ({
      value: point.id,
      label: formatPointLabel(point.name),
    })),
  ];

  return (
    <div
      style={{
        minHeight: 'calc(100vh - 112px)',
        display: 'flex',
        gap: 18,
        position: 'relative',
      }}
    >
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background:
            'radial-gradient(circle at 18% 20%, rgba(232, 184, 109, 0.10), transparent 20%), radial-gradient(circle at 80% 12%, rgba(255, 213, 152, 0.06), transparent 18%)',
          opacity: 0.85,
        }}
      />

      <aside
        style={{
          width: 298,
          minWidth: 298,
          background: '#0E0E0E',
          border: '1px solid #2A2A2A',
          borderRadius: 20,
          padding: 18,
          display: 'flex',
          flexDirection: 'column',
          gap: 18,
          overflow: 'auto',
          boxShadow: '0 24px 64px rgba(0, 0, 0, 0.28)',
          position: 'relative',
          zIndex: 1,
        }}
      >
        <div>
          <Space align="center" size={12}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 12,
                display: 'grid',
                placeItems: 'center',
                background: 'linear-gradient(135deg, #FFD598 0%, #E8B86D 100%)',
                color: '#281800',
              }}
            >
              <RobotOutlined />
            </div>
            <div>
              <Typography.Title level={4} style={{ color: '#E8B86D', margin: 0 }}>
                Japonica ИИ
              </Typography.Title>
              <Typography.Text style={{ color: '#9B8F7F', fontSize: 11, letterSpacing: '0.16em', textTransform: 'uppercase' }}>
                Аналитическая консоль
              </Typography.Text>
            </div>
          </Space>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <PageSectionLabel>Быстрые подсказки</PageSectionLabel>
          <Space direction="vertical" size={10} style={{ width: '100%' }}>
            {quickInsights.map((item) => (
              <PromptButton
                key={item.title}
                title={item.title}
                subtitle={item.question}
                icon={item.icon}
                onClick={() => handlePrefill(item.question)}
              />
            ))}
          </Space>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <PageSectionLabel>Готовые сценарии</PageSectionLabel>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {SAVED_SCENARIOS.map((scenario) => (
              <button
                key={scenario.title}
                type="button"
                onClick={() => handlePrefill(scenario.question)}
                style={{
                  width: '100%',
                  padding: 12,
                  borderRadius: 14,
                  background: '#201F1F',
                  border: '1px solid #2A2A2A',
                  color: '#E5E2E1',
                  textAlign: 'left',
                  cursor: 'pointer',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <HistoryOutlined style={{ color: '#E8B86D', flexShrink: 0 }} />
                  <Typography.Text strong style={{ color: '#E5E2E1', fontSize: 13 }}>
                    {scenario.title}
                  </Typography.Text>
                </div>
                <Typography.Text style={{ color: '#BFB6A8', fontSize: 11, lineHeight: 1.4, display: 'block', whiteSpace: 'normal', wordBreak: 'break-word' }}>
                  {scenario.question}
                </Typography.Text>
              </button>
            ))}
          </div>
        </div>

        <div style={{ marginTop: 'auto' }}>
          <Card
            bordered={false}
            style={{
              background: '#131313',
              border: '1px solid #2A2A2A',
            }}
            styles={{ body: { padding: 14 } }}
          >
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <PageSectionLabel>Текущий доступ</PageSectionLabel>
              <Typography.Text style={{ color: '#E5E2E1', fontSize: 13 }}>
                {roleMeta[role].label}
              </Typography.Text>
              <Typography.Text style={{ color: '#9B8F7F', fontSize: 12, lineHeight: 1.5 }}>
                {roleMeta[role].description}
              </Typography.Text>
              <MonoBadge tone="accent">{roleMeta[role].focus}</MonoBadge>
            </Space>
          </Card>
        </div>
      </aside>

      <section
        style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
          position: 'relative',
          zIndex: 1,
        }}
      >
        <Card
          bordered={false}
          style={{
            background: 'rgba(14, 14, 14, 0.82)',
            backdropFilter: 'blur(18px)',
            border: '1px solid #2A2A2A',
            boxShadow: '0 20px 50px rgba(0, 0, 0, 0.18)',
            position: 'sticky',
            top: 0,
            zIndex: 20,
          }}
          styles={{ body: { padding: '14px 16px' } }}
        >
          <Space align="center" size={12} wrap style={{ width: '100%', justifyContent: 'space-between' }}>
            <Space align="center" size={12} wrap>
              <div>
                <Typography.Title level={4} style={{ color: '#E5E2E1', margin: 0 }}>
                  ИИ-ассистент
                </Typography.Title>
                <Typography.Text style={{ color: '#BFB6A8' }}>
                  Диалог для аналитики, поиска причин и рекомендуемых действий.
                </Typography.Text>
                <Space size={8} wrap style={{ marginTop: 8 }}>
                  <MonoBadge tone={assistantStatus.tone}>{assistantStatus.label}</MonoBadge>
                  <Typography.Text style={{ color: '#BFB6A8', fontSize: 12, lineHeight: 1.5 }}>
                    {assistantStatus.description}
                  </Typography.Text>
                </Space>
              </div>
            </Space>
            <Space align="center" size={10} wrap>
              <Select
                value={pointFilter}
                onChange={setPointFilter}
                loading={pointsQuery.isLoading}
                options={pointOptions}
                style={{ minWidth: 240 }}
                dropdownStyle={{ background: '#131313' }}
              />
              <MonoBadge tone="neutral">{selectedPointLabel}</MonoBadge>
              <MonoBadge tone={latestDoneTurn?.response?.provider ? 'accent' : 'neutral'}>
                {formatProviderLabel(latestDoneTurn?.response?.provider)}
              </MonoBadge>
              {latestDoneTurn?.response?.used_fallback ? <MonoBadge tone="warning">РЕЗЕРВНЫЙ РЕЖИМ</MonoBadge> : null}
            </Space>
          </Space>
        </Card>

        <div
          style={{
            flex: 1,
            minHeight: 0,
            overflow: 'auto',
            padding: '4px 2px 0 2px',
            position: 'relative',
          }}
        >
          <div style={{ maxWidth: 1180, margin: '0 auto', position: 'relative', zIndex: 1 }}>
            {turns.length === 0 ? (
              <div style={{ paddingTop: 12 }}>
                <EmptyState
                  onPickPrompt={handlePrefill}
                  scopeLabel={selectedPointLabel}
                  statusLabel={assistantStatus.label}
                  statusDescription={assistantStatus.description}
                  statusTone={assistantStatus.tone}
                />
              </div>
            ) : (
              <Space direction="vertical" size={18} style={{ width: '100%' }}>
                {turns.map((turn) => (
                  <Space key={turn.turnId} direction="vertical" size={12} style={{ width: '100%' }}>
                    <UserBubble question={turn.question} askedAt={turn.askedAt} />
                    <AssistantBubble
                      turn={turn}
                      onSuggestionPick={(value) => handlePrefill(value)}
                    />
                  </Space>
                ))}
              </Space>
            )}
            <div ref={scrollEndRef} />
          </div>
        </div>

        <div
          style={{
            padding: '2px 0 0 0',
            position: 'relative',
            zIndex: 5,
          }}
        >
          <div
            style={{
              background: 'linear-gradient(180deg, rgba(19, 19, 19, 0.05) 0%, rgba(19, 19, 19, 0.92) 24%, rgba(19, 19, 19, 0.98) 100%)',
              borderTop: '1px solid rgba(42, 42, 42, 0.92)',
              paddingTop: 14,
            }}
          >
            <div
              style={{
                maxWidth: 1180,
                margin: '0 auto',
              }}
            >
              <div
                style={{
                  position: 'relative',
                  background: '#2A2A2A',
                  border: '1px solid #4F4538',
                  borderRadius: 18,
                  padding: 12,
                  boxShadow: '0 24px 60px rgba(0, 0, 0, 0.26)',
                }}
              >
                <Space align="center" size={10} style={{ width: '100%' }}>
                  <div
                    style={{
                      width: 40,
                      height: 40,
                      borderRadius: 12,
                      display: 'grid',
                      placeItems: 'center',
                      background: '#131313',
                      color: '#E8B86D',
                      border: '1px solid #4F4538',
                      flexShrink: 0,
                    }}
                  >
                    <FileTextOutlined />
                  </div>
                  <Input
                    ref={inputRef}
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    onPressEnter={(event) => {
                      event.preventDefault();
                      void handleSubmit();
                    }}
                    placeholder="Спросите о точках, аномалиях или динамике показателей..."
                    disabled={chatMutation.isPending}
                    size="large"
                    style={{
                      background: 'transparent',
                      border: 'none',
                      boxShadow: 'none',
                      color: '#E5E2E1',
                      fontSize: 14,
                    }}
                  />
                  <Button
                    type="primary"
                    size="large"
                    icon={chatMutation.isPending ? <LoadingOutlined /> : <SendOutlined />}
                    onClick={() => {
                      void handleSubmit();
                    }}
                    loading={chatMutation.isPending}
                    style={{
                      minWidth: 132,
                      background: 'linear-gradient(135deg, #FFD598 0%, #E8B86D 100%)',
                      color: '#281800',
                    }}
                  >
                    Отправить
                  </Button>
                </Space>
                <Space
                  align="center"
                  size={12}
                  wrap
                  style={{ marginTop: 10, justifyContent: 'space-between', width: '100%' }}
                >
                  <Space size={8} wrap>
                    <MonoBadge tone="neutral">Чат ассистента</MonoBadge>
                    <MonoBadge tone="neutral">{`Контур: ${selectedPointLabel}`}</MonoBadge>
                  </Space>
                  <Typography.Text style={{ color: '#9B8F7F', fontSize: 11 }}>
                    {chatMutation.isPending ? 'Генерируем ответ...' : 'Сообщение отправляется клавишей ввода.'}
                  </Typography.Text>
                </Space>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
