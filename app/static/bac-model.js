/* The supplied illustrative model, with ethanol g / body kg converted to BAC %. */
(function(root){
 function validate(p){
  const positive=(v,max)=>Number.isFinite(v)&&v>0&&v<=max;
  if(!positive(p.massKg,500)||!positive(p.distribution,2)||!Number.isFinite(p.eliminationPercentPerHour)||p.eliminationPercentPerHour<0||p.eliminationPercentPerHour>1||!positive(p.hours,72))throw Error('Invalid body mass, distribution, elimination or time range');
  if(!Array.isArray(p.drinks)||!p.drinks.length||p.drinks.length>100)throw Error('Use 1–100 drinks');
  for(const d of p.drinks)if(!Number.isFinite(d.timeHours)||d.timeHours<0||d.timeHours>p.hours||!Number.isFinite(d.ethanolG)||d.ethanolG<0||d.ethanolG>2000||!positive(d.absorptionPerHour,100))throw Error('Invalid drink time, ethanol amount or absorption rate');
 }
 function bacAt(time,p,drinks=p.drinks){
  const absorbed=drinks.reduce((sum,d)=>time<d.timeHours?sum:sum+0.1*d.ethanolG/(p.massKg*p.distribution)*(-Math.expm1(-d.absorptionPerHour*(time-d.timeHours))),0);
  return Math.max(0,absorbed-p.eliminationPercentPerHour*time);
 }
 function series(p){validate(p);const points=[];const count=Math.ceil(p.hours*60);for(let i=0;i<=count;i++){const time=i*p.hours/count;points.push({timeHours:time,bacPercent:bacAt(time,p),firstDrinkPercent:bacAt(time,p,[p.drinks[0]])});}return points;}
 function ethanolFromVolume(ml,abv){if(!Number.isFinite(ml)||ml<0||!Number.isFinite(abv)||abv<0||abv>100)throw Error('Invalid drink volume or ABV');return ml*abv/100*.789;}
 const model={validate,bacAt,series,ethanolFromVolume};root.FrissBAC=model;if(typeof module!=='undefined')module.exports=model;
})(globalThis);
