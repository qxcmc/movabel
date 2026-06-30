interface Window {
  __movabelServerStartedByApp?: boolean;
}

declare module 'virtual:changelog' {
  const raw: string;
  export default raw;
}
