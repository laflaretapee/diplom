import type { Role } from './types';

export const roleMeta: Record<
  Role,
  {
    label: string;
    description: string;
    accent: string;
    focus: string;
  }
> = {
  super_admin: {
    label: 'Суперадмин',
    description: 'Управляет пользователями, точками и доступом по всей системе.',
    accent: '#E8B86D',
    focus: 'Администрирование и контроль доступа',
  },
  franchisee: {
    label: 'Франчайзи',
    description: 'Управляет своими точками и отслеживает их показатели.',
    accent: '#DDC39E',
    focus: 'Контроль нескольких точек и локальной эффективности',
  },
  point_manager: {
    label: 'Менеджер точки',
    description: 'Управляет одной точкой и контролирует поток заказов.',
    accent: '#CBB18E',
    focus: 'Заказы, персонал и готовность точки',
  },
  staff: {
    label: 'Сотрудник',
    description: 'Работает по живой очереди заказов своей точки.',
    accent: '#B89A6A',
    focus: 'Очередь заказов и быстрое выполнение на кухне',
  },
};
