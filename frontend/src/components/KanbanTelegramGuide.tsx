import { CopyOutlined, LinkOutlined, SendOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Card, Space, Tag, Typography } from 'antd';
import { useState } from 'react';

import { apiClient } from '../api/client';
import { useIsMobileLayout } from '../hooks/useIsMobileLayout';

type TelegramStatusResponse = {
  linked: boolean;
  chat_id: string | null;
};

type TelegramLinkResponse = {
  code: string;
  expires_in: number;
  instructions: string;
};

type KanbanTelegramGuideProps = {
  compact?: boolean;
};

async function fetchTelegramStatus(): Promise<TelegramStatusResponse> {
  const { data } = await apiClient.get<TelegramStatusResponse>('/v1/notifications/telegram/status');
  return data;
}

export function KanbanTelegramGuide({ compact = false }: KanbanTelegramGuideProps) {
  const isMobile = useIsMobileLayout();
  const queryClient = useQueryClient();
  const [linkPayload, setLinkPayload] = useState<TelegramLinkResponse | null>(null);

  const statusQuery = useQuery({
    queryKey: ['telegram-status'],
    queryFn: fetchTelegramStatus,
  });

  const linkMutation = useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post<TelegramLinkResponse>('/v1/notifications/telegram/link', {});
      return data;
    },
    onSuccess: (data) => {
      setLinkPayload(data);
    },
  });

  const unlinkMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post('/v1/notifications/telegram/unlink', {});
    },
    onSuccess: async () => {
      setLinkPayload(null);
      await queryClient.invalidateQueries({ queryKey: ['telegram-status'] });
    },
  });

  const instructionItems = [
    'Нажмите «Получить код», чтобы сгенерировать одноразовую команду привязки.',
    'Откройте Telegram-бота и отправьте команду вида /link 123456.',
    'После привязки бот уведомляет о назначении карточки, смене дедлайна и просрочке задачи.',
    'Команда /tasks в боте показывает ваши текущие kanban-карточки.',
  ];

  return (
    <Card
      styles={{
        body: {
          padding: compact ? 16 : isMobile ? 16 : 20,
        },
      }}
    >
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Space
          direction={isMobile ? 'vertical' : 'horizontal'}
          size={12}
          style={{ width: '100%', justifyContent: 'space-between' }}
        >
          <Space direction="vertical" size={2}>
            <Typography.Title level={compact ? 5 : 4} style={{ margin: 0 }}>
              Telegram и канбан
            </Typography.Title>
            <Typography.Text type="secondary">
              Уведомления приходят в бот по рабочим карточкам и дедлайнам.
            </Typography.Text>
          </Space>
          <Tag color={statusQuery.data?.linked ? 'success' : 'default'} style={{ marginInlineEnd: 0 }}>
            {statusQuery.data?.linked ? 'Бот привязан' : 'Бот не привязан'}
          </Tag>
        </Space>

        {statusQuery.data?.linked && statusQuery.data.chat_id && !compact ? (
          <Typography.Text type="secondary">
            Активный chat id: {statusQuery.data.chat_id}
          </Typography.Text>
        ) : null}

        {compact ? (
          <Typography.Text type="secondary">
            Бот присылает уведомления о назначении карточки, дедлайне и просрочке. Команда `/tasks`
            показывает ваши активные задачи.
          </Typography.Text>
        ) : (
          <>
            <Space wrap size={[8, 8]}>
              <Tag color="blue">Назначение</Tag>
              <Tag color="gold">Дедлайн</Tag>
              <Tag color="red">Просрочка</Tag>
              <Tag color="default">/tasks</Tag>
            </Space>

            {instructionItems.map((item, index) => (
              <Typography.Text key={item} type="secondary">
                {index + 1}. {item}
              </Typography.Text>
            ))}
          </>
        )}

        {linkPayload ? (
          <Alert
            type="info"
            showIcon
            message={`Код для привязки: ${linkPayload.code}`}
            description={
              <Space direction="vertical" size={6} style={{ width: '100%' }}>
                <Typography.Text type="secondary">
                  Код действует {Math.max(1, Math.round(linkPayload.expires_in / 60))} минут.
                </Typography.Text>
                <Typography.Text code copyable={{ text: `/link ${linkPayload.code}` }}>
                  /link {linkPayload.code}
                </Typography.Text>
              </Space>
            }
          />
        ) : null}

        {statusQuery.isError ? (
          <Alert
            type="warning"
            showIcon
            message="Не удалось получить статус Telegram-бота"
            description="Повторите запрос чуть позже."
          />
        ) : null}

        <Space
          direction={isMobile ? 'vertical' : 'horizontal'}
          size={8}
          style={{ width: '100%' }}
        >
          <Button
            type="primary"
            icon={<LinkOutlined />}
            block={isMobile}
            loading={linkMutation.isPending}
            onClick={() => linkMutation.mutate()}
          >
            {statusQuery.data?.linked ? 'Обновить код привязки' : 'Получить код'}
          </Button>
          {linkPayload ? (
            <Button
              icon={<CopyOutlined />}
              block={isMobile}
              onClick={() => {
                void navigator.clipboard?.writeText(`/link ${linkPayload.code}`);
              }}
            >
              Скопировать команду
            </Button>
          ) : null}
          {statusQuery.data?.linked ? (
            <Button
              danger
              icon={<SendOutlined />}
              block={isMobile}
              loading={unlinkMutation.isPending}
              onClick={() => unlinkMutation.mutate()}
            >
              Отвязать бота
            </Button>
          ) : null}
        </Space>
      </Space>
    </Card>
  );
}
