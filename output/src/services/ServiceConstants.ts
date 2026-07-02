// src/services/ServiceConstants.ts

export const ServiceConstants = {
  NETWORK: 'NETWORK',
  PAGE_ROUTER: 'PAGE_ROUTER',
} as const;

// Type export for convenience
export type ServiceConstantsType = typeof ServiceConstants[keyof typeof ServiceConstants];