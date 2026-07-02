import React, { createContext, useContext, useState, useCallback, useRef } from 'react';
import LoginMainModel from '../models/LoginMainModel';

interface LoginMainViewModel {
  model: LoginMainModel;
  phone: string;
  code: string;
  phoneInputChange: (text: string) => void;
  codeInputChange: (text: string) => void;
  changeObtainCodeState: (callback: () => void) => void;
  phoneFocusRef: React.RefObject<any>;
  codeFocusRef: React.RefObject<any>;
}

const LoginMainContext = createContext<LoginMainViewModel | undefined>(undefined);

export const useLoginMainViewModel = () => {
  const context = useContext(LoginMainContext);
  if (!context) {
    throw new Error('useLoginMainViewModel must be used within a LoginMainProvider');
  }
  return context;
};

export const LoginMainProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [model, setModel] = useState<LoginMainModel>(new LoginMainModel());
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const phoneFocusRef = useRef(null);
  const codeFocusRef = useRef(null);

  const phoneInputChange = useCallback(
    (text: string) => {
      setPhone(text);
      setModel((prev: LoginMainModel) => ({
        ...prev,
        phoneNumber: text,
        obtainCodeEnable: text.length === 11,
        verifyLoginEnable: text.length === 11 && code.length === 6,
      }));
    },
    [code]
  );

  const codeInputChange = useCallback(
    (text: string) => {
      setCode(text);
      setModel((prev: LoginMainModel) => ({
        ...prev,
        verifyCode: text,
        verifyLoginEnable: phone.length === 11 && text.length === 6,
      }));
    },
    [phone]
  );

  const changeObtainCodeState = useCallback((callback: () => void) => {
    setModel((prev: LoginMainModel) => ({ ...prev, obtainCodeTitle: '重新获取' }));
    callback();
  }, []);

  return (
    <LoginMainContext.Provider
      value={{
        model,
        phone,
        code,
        phoneInputChange,
        codeInputChange,
        changeObtainCodeState,
        phoneFocusRef,
        codeFocusRef,
      }}>
      {children}
    </LoginMainContext.Provider>
  );
};
