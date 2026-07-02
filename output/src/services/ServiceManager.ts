// src/services/ServiceManager.ts

export interface ServiceProtocol {
  onLoad(): void;
  onUnLoad(): void;
}

class ServiceManager {
  private hashMap: Record<string, ServiceProtocol> = {};

  private static sInstance: ServiceManager | null = null;

  static getInstance(): ServiceManager {
    if (!ServiceManager.sInstance) {
      ServiceManager.sInstance = new ServiceManager();
    }
    return ServiceManager.sInstance;
  }

  setProtocol(name: string, component: ServiceProtocol): void {
    this.hashMap[name] = component;
  }

  getProtocol(name: string): ServiceProtocol {
    // Dart's `as ServiceProtocol` cast is a no-op in TypeScript; 
    // returning the value ensures type safety.
    return this.hashMap[name]!;
  }
}

export { ServiceManager };