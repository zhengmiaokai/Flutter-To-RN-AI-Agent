import { NetworkProtocol } from './service_interface';

export class CommonNetwork implements NetworkProtocol {
  onLoad(): void {
    // no-op
  }

  onUnLoad(): void {
    // no-op
  }

  post(uri: string, params: Record<string, any>, callback: (body: string | null, error: object | null) => void): void {
    const headers = { 'Content-Type': 'application/json' };
    const body = JSON.stringify(params);

    fetch(uri, {
      method: 'POST',
      headers,
      body,
    })
      .then((response) => {
        if (response.ok) {
          response.text().then((text) => callback(text, null));
        } else {
          response.text().then((text) => callback(null, new Error(text)));
        }
      })
      .catch((error: unknown) => {
        callback(null, error as object | null);
      });
  }
}