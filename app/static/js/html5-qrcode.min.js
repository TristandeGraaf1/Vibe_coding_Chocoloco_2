(function(window){
    // Minimal Html5Qrcode shim that uses jsQR for decoding frames.
    function Html5Qrcode(elementId){
        this._elementId = elementId;
        this._video = null;
        this._canvas = null;
        this._ctx = null;
        this._stream = null;
        this._raf = null;
        this._running = false;
    }

    Html5Qrcode.prototype.start = function(cameraConfig, config, onSuccess, onError){
        var self = this;
        return new Promise(function(resolve, reject){
            if(!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia){
                var err = new Error('Camera API niet beschikbaar');
                if(onError) onError(err);
                return reject(err);
            }

            var el = document.getElementById(self._elementId);
            if(!el){
                var err2 = new Error('Element niet gevonden: ' + self._elementId);
                if(onError) onError(err2);
                return reject(err2);
            }

            try{
                el.innerHTML = '';
                self._video = document.createElement('video');
                self._video.setAttribute('playsinline','');
                self._video.style.width = '100%';
                el.appendChild(self._video);

                self._canvas = document.createElement('canvas');
                self._ctx = self._canvas.getContext('2d');

                var videoConstraints = cameraConfig && cameraConfig.facingMode ? { facingMode: cameraConfig.facingMode } : true;
                navigator.mediaDevices.getUserMedia({ video: videoConstraints }).then(function(stream){
                    self._stream = stream;
                    self._video.srcObject = stream;
                    self._video.play().then(function(){
                        self._running = true;
                        function scanFrame(){
                            if(!self._running) return;
                            if(self._video.readyState === self._video.HAVE_ENOUGH_DATA){
                                self._canvas.width = self._video.videoWidth;
                                self._canvas.height = self._video.videoHeight;
                                self._ctx.drawImage(self._video, 0, 0, self._canvas.width, self._canvas.height);
                                try{
                                    if(window.jsQR){
                                        var imageData = self._ctx.getImageData(0,0,self._canvas.width,self._canvas.height);
                                        var code = jsQR(imageData.data, self._canvas.width, self._canvas.height);
                                        if(code && code.data){
                                            if(onSuccess) onSuccess(code.data);
                                            // keep running until stop called by caller; but stop automatically to mimic html5-qrcode
                                            // stop and resolve
                                            self.stop().then(function(){ /*noop*/ });
                                            return;
                                        }
                                    }
                                }catch(e){
                                    if(onError) onError(e);
                                }
                            }
                            self._raf = requestAnimationFrame(scanFrame);
                        }
                        self._raf = requestAnimationFrame(scanFrame);
                        resolve();
                    }).catch(function(playErr){
                        if(onError) onError(playErr);
                        reject(playErr);
                    });
                }).catch(function(streamErr){
                    if(onError) onError(streamErr);
                    reject(streamErr);
                });
            }catch(e){
                if(onError) onError(e);
                reject(e);
            }
        });
    };

    Html5Qrcode.prototype.stop = function(){
        var self = this;
        return new Promise(function(resolve, reject){
            try{
                self._running = false;
                if(self._raf){ cancelAnimationFrame(self._raf); self._raf = null; }
                if(self._video && self._video.srcObject){
                    var s = self._video.srcObject;
                    if(s.getTracks){ s.getTracks().forEach(function(t){ t.stop(); }); }
                    self._video.srcObject = null;
                }
                if(self._video && self._video.parentNode){ self._video.parentNode.removeChild(self._video); }
                self._video = null;
                self._canvas = null;
                self._ctx = null;
                self._stream = null;
                resolve();
            }catch(e){ reject(e); }
        });
    };

    Html5Qrcode.prototype.clear = function(){
        // no-op for compatibility
        return Promise.resolve();
    };

    window.Html5Qrcode = Html5Qrcode;
})(window);
