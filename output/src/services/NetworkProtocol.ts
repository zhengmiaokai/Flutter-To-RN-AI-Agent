import { ServiceProtocol } from './service_manager';

export abstract class NetworkProtocol implements ServiceProtocol {
  abstract onLoad(): void;
  abstract onUnLoad(): void;
  abstract post(
    uri: string,
    params: Record<string, any>,
    callback: (body: string | null, error: object | null) => void,
  ): void;
}