// ====================================
// JavaScript para Agendamento
// Centro Estética Automotiva
// ====================================

document.addEventListener('DOMContentLoaded', function() {
    
    // ==================== SELEÇÃO DE SERVIÇOS ====================
    const cardsServico = document.querySelectorAll('.card-servico');
    let servicoSelecionado = null;
    
    if (cardsServico.length > 0) {
        cardsServico.forEach(card => {
            card.addEventListener('click', function() {
                // Remove seleção anterior
                cardsServico.forEach(c => c.classList.remove('selecionado'));
                
                // Seleciona atual
                this.classList.add('selecionado');
                servicoSelecionado = this.dataset.servicoId;
                
                // Atualiza resumo
                atualizarResumo();
                
                // Habilita próximo passo
                document.getElementById('btn-proximo-servico').disabled = false;
            });
        });
    }
    
    // ==================== CALENDÁRIO ====================
    const calendarioDays = document.querySelectorAll('.calendario-day:not(.nome-dia)');
    let dataSelecionada = null;
    
    if (calendarioDays.length > 0) {
        const monthNames = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
                      "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
        
        let currentDate = new Date();
        let currentMonth = currentDate.getMonth();
        let currentYear = currentDate.getFullYear();
        
        function renderCalendar(month, year) {
            const firstDay = new Date(year, month, 1).getDay();
            const daysInMonth = new Date(year, month + 1, 0).getDate();
            const monthLabel = document.getElementById('month-label');
            
            if (monthLabel) {
                monthLabel.textContent = `${monthNames[month]} de ${year}`;
            }
            
            const daysContainer = document.getElementById('calendario-days');
            if (!daysContainer) return;
            
            daysContainer.innerHTML = '';
            
            const dayNames = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
            dayNames.forEach(day => {
                const dayElem = document.createElement('div');
                dayElem.className = 'calendario-day nome-dia';
                dayElem.textContent = day;
                daysContainer.appendChild(dayElem);
            });
            
            //空白天
            for (let i = 0; i < firstDay; i++) {
                const emptyDay = document.createElement('div');
                emptyDay.className = 'calendario-day';
                emptyDay.style.visibility = 'hidden';
                daysContainer.appendChild(emptyDay);
            }
            
            // Dias
            for (let day = 1; day <= daysInMonth; day++) {
                const date = new Date(year, month, day);
                const today = new Date();
                today.setHours(0, 0, 0, 0);
                
                const dayElem = document.createElement('div');
                dayElem.className = 'calendario-day';
                dayElem.textContent = day;
                
                if (date < today) {
                    dayElem.classList.add('disabled');
                } else if (date.getDay() === 0) {
                    // Domingo - não disponível
                    dayElem.classList.add('disabled');
                } else {
                    dayElem.addEventListener('click', function() {
                        selectDate(date);
                    });
                }
                
                if (dataSelecionada && date.getTime() === dataSelecionada.getTime()) {
                    dayElem.classList.add('selecionado');
                }
                
                daysContainer.appendChild(dayElem);
            }
        }
        
        function selectDate(date) {
            dataSelecionada = date;
            
            // Atualiza visual
            document.querySelectorAll('.calendario-day').forEach(d => d.classList.remove('selecionado'));
            event.target.classList.add('selecionado');
            
            // Atualiza resumo
            atualizarResumo();
            
            // Carrega horários disponíveis
            carregarHorarios(date);
        }
        
        // Botões de navegação
        const prevBtn = document.getElementById('prev-month');
        const nextBtn = document.getElementById('next-month');
        
        if (prevBtn) {
            prevBtn.addEventListener('click', function() {
                currentMonth--;
                if (currentMonth < 0) {
                    currentMonth = 11;
                    currentYear--;
                }
                renderCalendar(currentMonth, currentYear);
            });
        }
        
        if (nextBtn) {
            nextBtn.addEventListener('click', function() {
                currentMonth++;
                if (currentMonth > 11) {
                    currentMonth = 0;
                    currentYear++;
                }
                renderCalendar(currentMonth, currentYear);
            });
        }
        
        // Inicializa calendário
        renderCalendar(currentMonth, currentYear);
    }
    
    // ==================== HORÁRIOS ====================
    let horarioSelecionado = null;
    
    function carregarHorarios(data) {
        const container = document.getElementById('horarios-container');
        if (!container) return;
        
        // Mostra loading
        container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
        
        // Simula carregamento (em produção, faria uma requisição AJAX)
        setTimeout(function() {
            const horarios = [
                '08:00', '08:30', '09:00', '09:30', '10:00', '10:30',
                '11:00', '11:30', '13:00', '13:30', '14:00', '14:30',
                '15:00', '15:30', '16:00', '16:30', '17:00', '17:30'
            ];
            
            // Simula alguns horários ocupados
            const ocupados = ['09:00', '14:00', '15:30'];
            
            container.innerHTML = '';
            
            horarios.forEach(horario => {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'horario-btn';
                btn.textContent = horario;
                btn.dataset.horario = horario;
                
                if (ocupados.includes(horario)) {
                    btn.classList.add('indisponivel');
                    btn.disabled = true;
                } else {
                    btn.addEventListener('click', function() {
                        selectHorario(horario);
                    });
                }
                
                if (horarioSelecionado === horario) {
                    btn.classList.add('selecionado');
                }
                
                container.appendChild(btn);
            });
        }, 500);
    }
    
    function selectHorario(horario) {
        horarioSelecionado = horario;
        
        // Atualiza visual
        document.querySelectorAll('.horario-btn').forEach(b => b.classList.remove('selecionado'));
        document.querySelector(`[data-horario="${horario}"]`).classList.add('selecionado');
        
        // Atualiza resumo
        atualizarResumo();
    }
    
    // ==================== RESUMO DO AGENDAMENTO ====================
    function atualizarResumo() {
        const servicoNome = document.querySelector('.card-servico.selecionado .servico-nome');
        const servicoPreco = document.querySelector('.card-servico.selecionado .preco');
        
        const servicoEl = document.getElementById('resumo-servico');
        const dataEl = document.getElementById('resumo-data');
        const horarioEl = document.getElementById('resumo-horario');
        const totalEl = document.getElementById('resumo-total');
        
        if (servicoEl && servicoNome) {
            servicoEl.textContent = servicoNome.textContent;
        }
        
        if (dataEl && dataSelecionada) {
            const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
            dataEl.textContent = dataSelecionada.toLocaleDateString('pt-BR', options);
        }
        
        if (horarioEl && horarioSelecionado) {
            horarioEl.textContent = horarioSelecionado + 'h';
        }
        
        if (totalEl && servicoPreco) {
            totalEl.textContent = servicoPreco.textContent;
        }
    }
    
    // ==================== BOTÃO CONFIRMAR ====================
    const btnConfirmar = document.getElementById('btn-confirmar');
    
    if (btnConfirmar) {
        btnConfirmar.addEventListener('click', function() {
            if (!servicoSelecionado || !dataSelecionada || !horarioSelecionado) {
                alert('Por favor, complete todas as etapas do agendamento.');
                return;
            }
            
            //製作WhatsApp連結
            const telefone = this.dataset.telefone || '';
            const nome = document.getElementById('cliente_nome')?.value || 'Cliente';
            const servicoNome = document.querySelector('.card-servico.selecionado .servico-nome')?.textContent || '';
            const dataFormatada = dataSelecionada.toLocaleDateString('pt-BR');
            
            const mensagem = `Quero agendar ${servicoNome} para ${dataFormatada} às ${horarioSelecionado}h. Meu nome é ${nome}.`;
            
            //移除空格
            const telefoneLimpo = telefone.replace(/\D/g, '');
            const whatsAppUrl = `https://wa.me/55${telefoneLimpo}?text=${encodeURIComponent(mensagem)}`;
            
            //打開WhatsApp
            window.open(whatsAppUrl, '_blank');
            
            //显示成功消息
            showMessage('Agendamento iniciado no WhatsApp! Complete a confirmação enviando a mensagem.', 'sucesso');
        });
    }
    
    // ==================== MENSAGENS ====================
    function showMessage(text, type) {
        const container = document.getElementById('messages');
        if (!container) return;
        
        const msg = document.createElement('div');
        msg.className = `mensagem mensagem-${type}`;
        msg.textContent = text;
        
        container.appendChild(msg);
        
        // Auto remove após 5秒
        setTimeout(() => {
            msg.remove();
        }, 5000);
    }
    
    // ==================== VALIDAÇÃO DO FORMULÁRIO ====================
    const formAgendamento = document.getElementById('form-agendamento');
    
    if (formAgendamento) {
        formAgendamento.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const nome = document.getElementById('cliente_nome').value;
            const telefone = document.getElementById('cliente_telefone').value;
            
            if (!nome || !telefone) {
                showMessage('Preencha seu nome e telefone.', 'erro');
                return;
            }
            
            if (!servicoSelecionado) {
                showMessage('Selecione um serviço.', 'erro');
                return;
            }
            
            if (!dataSelecionada) {
                showMessage('Selecione uma data.', 'erro');
                return;
            }
            
            if (!horarioSelecionado) {
                showMessage('Selecione um horário.', 'erro');
                return;
            }
            
            // 可選：发送數據到服務器
            const formData = new FormData();
            formData.append('servico', servicoSelecionado);
            formData.append('data', dataSelecionada.toISOString().split('T')[0]);
            formData.append('horario', horarioSelecionado);
            formData.append('nome', nome);
            formData.append('telefone', telefone);
            
            // 模擬提交
            console.log('Dados do agendamento:', Object.fromEntries(formData));
            
            // 顯示成功
            showMessage('Agendamento realizado com sucesso!', 'sucesso');
            
            // 重置表單
            formAgendamento.reset();
        });
    }
    
    // ==================== MÁSCARA DE TELEFONE ====================
    const telefoneInput = document.getElementById('cliente_telefone');
    
    if (telefoneInput) {
        telefoneInput.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\D/g, '');
            
            if (value.length > 11) {
                value = value.slice(0, 11);
            }
            
            if (value.length >= 2) {
                value = `(${value.slice(0, 2)}) ${value.slice(2)}`;
            }
            
            if (value.length > 10) {
                value = `${value.slice(0, 10)}-${value.slice(10)}`;
            }
            
            e.target.value = value;
        });
    }
    
    // ==================== smooth scroll ====================
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // ==================== ANIMAÇÕES DE SCROLL ====================
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-in');
            }
        });
    }, observerOptions);
    
    document.querySelectorAll('.card, .galeria-item').forEach(el => {
        observer.observe(el);
    });
});


function formatarTelefone(valor) {
    if (!valor) return '';
    
    const numeros = valor.replace(/\D/g, '');
    
    if (numeros.length === 10) {
        return `(${numeros.slice(0, 2)}) ${numeros.slice(2, 6)}-${numeros.slice(6)}`;
    } else if (numeros.length === 11) {
        return `(${numeros.slice(0, 2)}) ${numeros.slice(2, 3)} ${numeros.slice(3, 7)}-${numeros.slice(7)}`;
    }
    
    return valor;
}


function gerarLinkWhatsApp(telefone, mensagem) {
    const telefoneLimpo = telefone.replace(/\D/g, '');
    const url = `https://wa.me/55${telefoneLimpo}?text=${encodeURIComponent(mensagem)}`;
    return url;
}


function obterDiaSemana(data) {
    const dias = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado'];
    return dias[data.getDay()];
}


function obterDiaSemanaCurto(data) {
    const dias = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
    return dias[data.getDay()];
}
