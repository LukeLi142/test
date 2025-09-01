//選擇預約日期

const 選擇日期 = document.querySelector('.選擇日期');

document.addEventListener('DOMContentLoaded', function() {
   
    const calendar = flatpickr(選擇日期, {
        locale: 'zh_tw',
        dateFormat: 'Y-m-d',
        minDate: 'today',
        maxDate: new Date().fp_incr(10), // 10天後
        //輸入用戶選擇的日期
        onChange: function(selectedDates, dateStr, instance) {
            console.log("選到日期:", dateStr);
            document.getElementById('datepicker').value = dateStr;
        }
    });

    選擇日期.addEventListener('click', function() {
        calendar.open();
    });
});

