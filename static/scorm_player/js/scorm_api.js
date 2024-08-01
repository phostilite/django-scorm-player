class SCORMAPI {
    constructor() {
        this.data = {};
    }

    LMSInitialize(str) {
        console.log("LMSInitialize called with: " + str);
        return "true";
    }

    LMSFinish(str) {
        console.log("LMSFinish called with: " + str);
        return "true";
    }

    LMSGetValue(element) {
        console.log("LMSGetValue called for: " + element);
        return this.data[element] || "";
    }

    LMSSetValue(element, value) {
        console.log("LMSSetValue called with: " + element + " = " + value);
        this.data[element] = value;
        return "true";
    }

    LMSCommit(str) {
        console.log("LMSCommit called with: " + str);
        return "true";
    }

    LMSGetLastError() {
        return "0";
    }

    LMSGetErrorString(errorCode) {
        return "No error";
    }

    LMSGetDiagnostic(errorCode) {
        return "No diagnostic information";
    }
}