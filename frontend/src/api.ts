import axios from 'axios';

// Automatically determine URL based on environment
const isProduction = import.meta.env.PROD;
const BASE_URL = isProduction ? window.location.origin : 'http://localhost:8000';

const api = axios.create({
    baseURL: BASE_URL,
});

export const getStatus = async () => {
    const response = await api.get('/status');
    return response.data;
};

export const controlLight = async (action: string, value: string | number | null = null) => {
    return await api.post('/control/light', { action, value });
};

export const controlFirestick = async (command: string) => {
    return await api.post('/control/firestick', { command });
};

export const sendChat = async (text: string, target: 'local' | 'esp' = 'esp') => {
    // target='esp' means "Speaks through ESP32"
    return await api.post('/chat/send', { text, target }, {
        responseType: target === 'local' ? 'blob' : 'json'
    });
};

export const speakText = async (text: string, target: 'local' | 'esp' = 'esp') => {
    return await api.post('/tts/speak', { text, target }, {
        responseType: target === 'local' ? 'blob' : 'json'
    });
};

export default api;
