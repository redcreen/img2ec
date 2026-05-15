"use client";
import { SWRConfig } from "swr";
import { ToastProvider } from "@/lib/useToast";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig value={{ revalidateOnFocus: false, dedupingInterval: 1000 }}>
      <ToastProvider>
        {children}
      </ToastProvider>
    </SWRConfig>
  );
}
