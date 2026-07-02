import React, { createContext, useContext, useMemo } from 'react';
import type { PropsWithChildren } from 'react';

// ---- LoginMainViewModel type (locally defined — not exported from LoginMainViewModel.tsx) ----
interface LoginMainViewModel {
  model: any;
  phone: string;
  code: string;
  phoneInputChange: (text: string) => void;
  codeInputChange: (text: string) => void;
  changeObtainCodeState: (callback: () => void) => void;
  phoneFocusRef: React.RefObject<any>;
  codeFocusRef: React.RefObject<any>;
}

// ---- Scene enum ----
export enum LoginScene {
  MainView,
  AccountLogin,
}

// Alias for backward compatibility with LoginPage.tsx
export const LoginScence = LoginScene;

// ---- LoginViewModel class (default export) ----
class LoginViewModel {
  loginScene: LoginScene;
  mainViewModel: LoginMainViewModel;

  constructor() {
    this.loginScene = LoginScene.MainView;
    this.mainViewModel = {} as LoginMainViewModel;
  }

  changeLoginScence() {
    this.loginScene =
      this.loginScene === LoginScene.MainView
        ? LoginScene.AccountLogin
        : LoginScene.MainView;
  }
}

export default LoginViewModel;

// ---- Context state shape ----
interface LoginViewModelState {
  loginScene: LoginScene;
  mainViewModel: LoginMainViewModel;
  changeLoginScence: () => void;
}

const LoginViewModelContext = createContext<LoginViewModelState | undefined>(undefined);

// ---- Provider (accepts a class instance via `value` prop) ----
export const LoginViewModelProvider: React.FC<
  PropsWithChildren & { value: LoginViewModel }
> = ({ children, value }) => {
  const contextValue = useMemo<LoginViewModelState>(
    () => ({
      loginScene: value.loginScene,
      mainViewModel: value.mainViewModel,
      changeLoginScence: () => value.changeLoginScence(),
    }),
    [value],
  );

  return (
    <LoginViewModelContext.Provider value={contextValue}>
      {children}
    </LoginViewModelContext.Provider>
  );
};

// ---- Hook ----
export const useLoginViewModel = (): LoginViewModelState => {
  const context = useContext(LoginViewModelContext);
  if (context === undefined) {
    throw new Error(
      'useLoginViewModel must be used within a LoginViewModelProvider',
    );
  }
  return context;
};
